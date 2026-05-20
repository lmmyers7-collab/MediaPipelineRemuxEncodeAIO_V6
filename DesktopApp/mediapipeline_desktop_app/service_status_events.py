from __future__ import annotations

from pathlib import Path
from typing import Any


def pipeline_event_data(event: dict[str, Any]) -> dict[str, Any]:
    data = event.get("data")
    return data if isinstance(data, dict) else {}


def format_pipeline_event_summary(events: list[dict[str, Any]], *, max_items: int = 8) -> list[str]:
    rows: list[str] = []
    for event in reversed(events[-max_items:]):
        event_type = str(event.get("event_type", "") or "").strip()
        status = str(event.get("status", "") or "").strip()
        stage = str(event.get("stage", "") or "").strip()
        route = str(event.get("route", "") or "").strip()
        source_path = str(event.get("source_path", "") or "").strip()
        data = pipeline_event_data(event)
        tool_name = str(data.get("tool_name", "") or "").strip()

        label_parts = [part for part in (event_type, status, stage or route, tool_name) if part]
        label = " | ".join(label_parts) if label_parts else "pipeline event"
        if source_path:
            label = f"{label} | {Path(source_path).name}"
        priority_requested = str(data.get("priority_requested", "") or "").strip().lower()
        priority_applied = data.get("priority_applied")
        if priority_requested and priority_requested != "inherit" and priority_applied is False:
            priority_error = str(data.get("priority_error", "") or "").strip()
            if priority_error:
                label = f"{label} | priority {priority_requested} requested but not applied: {priority_error}"
            else:
                label = f"{label} | priority {priority_requested} requested but not applied"
        rows.append(label)
    return rows


def pipeline_event_stage_label(stage: str, route: str, status: str = "") -> str:
    if stage == "encode_cpu":
        return "encode (CPU)"
    if stage == "encode":
        return "encode"
    if stage == "remux_av":
        return "remux"
    if stage == "copy_to_scratch":
        return "copy to scratch"
    if stage == "remux_prepare":
        return "remux preparation"
    if stage == "remux_mux":
        return "remux mux"
    if stage == "remux_verify":
        return "remux verify"
    if stage == "encode_prepare":
        return "encode preparation"
    if stage == "encode_verify":
        return "encode verify"
    if stage == "push":
        return "server push"
    if stage == "sidecar":
        return "sidecar write"
    if stage == "retry_pending_push":
        return "publishing parked outputs"
    if stage == "pending-push-park":
        if status == "output-space-deferred":
            return "parked until output space is available"
        if status == "deferred":
            return "parked for later publish"
        return "parked for retry"
    if stage == "processing":
        return "processing"
    if stage == "route":
        return f"{route} route" if route else "route selection"
    if stage == "scanning":
        return "scanning sources"
    if stage == "sleeping":
        return "idle / sleeping until next scan"
    if stage == "paused":
        return "paused"
    if stage == "stopped":
        return "stopped"
    if stage == "idle":
        return "idle / waiting for next item"
    if stage == "startup":
        return "initializing"
    if stage == "completed":
        return f"{route} complete" if route else "completed"
    if stage == "failed":
        return f"{route} failed" if route else "failed"
    return stage.replace("_", " ").strip()


def structured_status_from_pipeline_event(event: dict[str, Any]) -> str:
    event_type = str(event.get("event_type", "") or "").strip().lower()
    stage = str(event.get("stage", "") or "").strip().lower()
    route = str(event.get("route", "") or "").strip().lower()
    status = str(event.get("status", "") or "").strip().lower()
    data = pipeline_event_data(event)

    if event_type == "pipeline_started":
        return "initializing"
    if event_type == "job_started":
        return "processing"
    if event_type == "route_selected":
        return f"{route} selected" if route else "route selected"
    if event_type == "publish_parked":
        if status == "output-space-deferred":
            return "parked until output space is available"
        if status == "deferred":
            return "parked for later publish"
        return "parked for retry"
    if event_type == "publish_drained":
        if status == "already_published":
            return "server already published"
        if status in {"succeeded", "success", "complete", "completed"}:
            return "server push complete"
        if status == "failed":
            return "server push failed"
        return "publishing parked outputs"
    if event_type == "failure_recorded":
        return "failure recorded"

    base = pipeline_event_stage_label(stage, route, status)
    if not base:
        base = str(data.get("tool_name", "") or "").strip().lower()
    if event_type == "job_completed":
        if status in {"succeeded", "success", "complete", "completed"}:
            return f"{route} complete" if route else "completed"
        if status == "failed":
            return f"{route} failed" if route else "failed"
    if event_type == "tool_started":
        return f"{base} started" if base else "tool started"
    if event_type == "tool_completed":
        if status in {"succeeded", "success", "complete", "completed"}:
            return f"{base} complete" if base else "tool complete"
        if status == "failed":
            return f"{base} failed" if base else "tool failed"
        return f"{base} {status}".strip() if base and status else base
    if base:
        if status == "failed":
            return f"{base} failed"
        if status in {"succeeded", "success", "complete", "completed"}:
            return f"{base} complete"
        return base
    return ""
