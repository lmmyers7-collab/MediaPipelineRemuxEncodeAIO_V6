"""Application status, telemetry, and progress-bar policy helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from mediapipeline.core.telemetry.gpu_usage import gpu_encoder_usage_payload
from mediapipeline.desktop.models import Snapshot, TelemetrySnapshot


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

COMPLETE_PROGRESS_STATES = ("complete", "completed", "published", "deferred", "idle")

FAILED_PROGRESS_STATES = ("failed", "error", "blocked", "stopped")


def application_capabilities() -> list[str]:
    return list(APP_CAPABILITIES)


def int_from_mapping(mapping: Mapping[str, Any], *keys: str) -> int:
    for key in keys:
        raw = mapping.get(key)
        try:
            if raw not in (None, ""):
                return int(float(raw))
        except (TypeError, ValueError):
            continue
    return 0


def nullable_int_from_mapping(mapping: Mapping[str, Any], *keys: str) -> int | None:
    for key in keys:
        raw = mapping.get(key)
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
        raw = mapping.get(key)
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


def progress_state_status(*values: str, stale: bool = False) -> str:
    if stale:
        return "warning"
    text = " ".join(str(value or "").lower() for value in values)
    if any(token in text for token in FAILED_PROGRESS_STATES):
        return "blocked"
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
    payload = {
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
        {"id": "copy", "label": "Copy file", "status": copy_status},
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


def pipeline_progress_bars(progress: Mapping[str, Any], *, pipeline_state: str, stale: bool) -> list[dict[str, Any]]:
    if not progress:
        return []
    bars: list[dict[str, Any]] = []
    stage = text_from_mapping(progress, "CurrentStage", "Status")
    route = text_from_mapping(progress, "CurrentRoute", "Route")
    file_display = text_from_mapping(progress, "CurrentFileDisplay", "CurrentFile")
    queue_phase = text_from_mapping(progress, "CurrentQueuePhase")
    percent = float_from_mapping(progress, "CurrentStagePercent")
    status = progress_state_status(pipeline_state, text_from_mapping(progress, "Status"), stage, stale=stale)
    detail_parts = [part for part in (stage, route, file_display) if part]
    bars.append(
        progress_bar(
            bar_id="current_stage",
            label="Current stage",
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

    push_state = text_from_mapping(progress, "PushState")
    sidecar_state = text_from_mapping(progress, "SidecarState")
    copy_percent = float_from_mapping(progress, "CopyPercent")
    stage_lower = stage.lower()
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
                    label="Push file",
                    status=progress_state_status(push_state, stage, stale=stale),
                    percent=copy_percent,
                    detail=copy_detail,
                    source="pipeline_progress.json",
                    updated_at=text_from_mapping(progress, "CopyUpdatedAt", "LastUpdate", "UpdatedAt", "updated_at"),
                    stale=stale,
                )
            )
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


def audit_report_progress_bar(audit_progress: Mapping[str, Any], *, status_text: str) -> dict[str, Any] | None:
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
        status = progress_state_status(status_text, stage)
    return progress_bar(
        bar_id="audit_reports",
        label="Audit reports",
        status=status,
        percent=percent,
        mode="stepped",
        detail=" | ".join(detail_parts),
        source="audit_progress.json",
        updated_at=text_from_mapping(audit_progress, "last_update", "LastUpdate", "updated_at"),
    )


def audit_progress_bars(audit_progress: Mapping[str, Any]) -> list[dict[str, Any]]:
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
            status=progress_state_status(status_text),
            percent=percent,
            detail=detail,
            source="audit_progress.json",
            updated_at=text_from_mapping(audit_progress, "last_update", "LastUpdate", "updated_at"),
        )
    ]
    report_bar = audit_report_progress_bar(audit_progress, status_text=status_text)
    if report_bar is not None:
        bars.append(report_bar)
    return bars


def snapshot_progress_bars(snapshot: Snapshot, *, pipeline_state: str) -> list[dict[str, Any]]:
    progress = snapshot.progress or {}
    audit_progress = snapshot.audit_progress or {}
    stale = "stale progress" in str(snapshot.current_activity or "").lower()
    return [
        *pipeline_progress_bars(progress, pipeline_state=pipeline_state, stale=stale),
        *audit_progress_bars(audit_progress),
    ]


def optional_path_text(path: Path | None) -> str:
    return str(path) if path else ""


def snapshot_latest_paths(snapshot: Snapshot) -> dict[str, str]:
    latest_paths = {
        "latest_failure_report": optional_path_text(snapshot.latest_failure_report),
        "latest_failure_json": optional_path_text(snapshot.latest_failure_json),
        "latest_audit_csv": optional_path_text(snapshot.latest_audit_csv),
        "latest_priority_csv": optional_path_text(snapshot.latest_priority_csv),
    }
    return {key: value for key, value in latest_paths.items() if value}


def snapshot_warnings(snapshot: Snapshot) -> list[str]:
    if snapshot.last_error:
        return [str(snapshot.last_error)]
    return []


def snapshot_recent_events(snapshot: Snapshot, *, limit: int = 25) -> list[dict[str, Any]]:
    return [dict(item) for item in snapshot.pipeline_events[-limit:]]


def telemetry_sampled_at(telemetry: TelemetrySnapshot) -> str:
    if telemetry.collected_at is None:
        return ""
    if telemetry.collected_at.tzinfo:
        return telemetry.collected_at.astimezone().isoformat()
    return telemetry.collected_at.isoformat()


def telemetry_gpu_present(telemetry: TelemetrySnapshot) -> bool:
    return (
        telemetry.gpu_count > 0
        or telemetry.gpu_encoder_percent is not None
        or bool(str(telemetry.gpu_name or "").strip())
        or bool(telemetry.gpu_rows)
    )


def telemetry_fields(telemetry: TelemetrySnapshot) -> dict[str, Any]:
    return {
        "sampled_at": telemetry_sampled_at(telemetry),
        "cpu_percent": telemetry.cpu_percent,
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
