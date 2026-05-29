from __future__ import annotations

from typing import Any, Mapping


SCHEDULE_UNWATCHED_MODES = frozenset({"validate", "drain_pending_pushes"})
SCHEDULE_MODE_NOT_SCHEDULED_REASON = "mode_not_scheduled"
SCHEDULE_CONTINUOUS_BLOCK_MESSAGE = (
    "Continuous start is blocked while schedule enforcement is enabled because the local API "
    "does not have an available backend schedule-stop watcher. Use Run Once, Validate, or explicitly choose "
    "Ignore Schedule when you intend to bypass schedule enforcement."
)
SCHEDULE_OUTSIDE_WINDOW_MESSAGE = (
    "Pipeline start is outside the allowed schedule window. Choose Run Once outside schedule or "
    "Ignore Schedule explicitly before starting from the web shell."
)
SCHEDULE_CONTINUOUS_WATCHER_CHECK_KEY = "continuous_schedule_stop_watcher"
SCHEDULE_CONTINUOUS_WATCHER_LABEL = "Continuous schedule-stop watcher"


def normalize_schedule_override(value: Any) -> str:
    return str(value or "").strip().casefold().replace("-", "_")


def schedule_gate_data(enabled: bool, evaluation: Mapping[str, Any]) -> dict[str, Any]:
    data = {
        "checked": True,
        "enabled": bool(enabled),
        "allowed_now": bool(evaluation.get("allowed_now", True)),
        "status_text": str(evaluation.get("status_text") or ""),
    }
    for key in ("current_window_end", "next_allowed_start", "next_allowed_end", "next_transition"):
        if evaluation.get(key) is not None:
            data[key] = evaluation.get(key)
    return data


def _schedule_time_evidence(data: Mapping[str, Any]) -> str:
    return str(
        data.get("current_window_end")
        or data.get("next_allowed_end")
        or data.get("next_transition")
        or "none"
    )


def continuous_schedule_stop_watcher_preflight_check(
    *,
    requested_mode: str,
    actual_mode: str,
    request: Mapping[str, Any],
    schedule_gate: Mapping[str, Any],
    backend_watcher_available: bool = False,
) -> dict[str, Any]:
    """Describe whether a WebView continuous launch can rely on schedule-stop ownership."""
    data = schedule_gate.get("data") if isinstance(schedule_gate.get("data"), Mapping) else {}
    override = normalize_schedule_override(request.get("schedule_override"))
    enabled = bool(data.get("enabled", False))
    allowed_now = bool(data.get("allowed_now", True))
    next_stop = _schedule_time_evidence(data)
    status_text = str(data.get("status_text") or "(not reported)")
    detail = [
        "WebView/local API can evaluate schedule gates, but it does not yet own the continuous-run stop-at-window-end watcher.",
        "V5 remains the fallback for scheduled continuous runs that must automatically request Stop After Current when the window closes.",
        {
            "requested_mode": requested_mode,
            "actual_mode": actual_mode,
            "schedule_enabled": enabled,
            "allowed_now": allowed_now,
            "override": override or "none",
            "next_schedule_stop": next_stop,
            "status_text": status_text,
            "backend_watcher_owned": backend_watcher_available,
        },
    ]
    if requested_mode != "continuous":
        return {
            "key": SCHEDULE_CONTINUOUS_WATCHER_CHECK_KEY,
            "label": SCHEDULE_CONTINUOUS_WATCHER_LABEL,
            "status": "ready",
            "evidence": f"requested_mode={requested_mode}; watcher not required.",
            "action": "No schedule-stop watcher is required for this pipeline mode.",
            "detail": detail,
        }
    if not enabled:
        return {
            "key": SCHEDULE_CONTINUOUS_WATCHER_CHECK_KEY,
            "label": SCHEDULE_CONTINUOUS_WATCHER_LABEL,
            "status": "ready",
            "evidence": "Schedule enforcement is off; watcher is not armed.",
            "action": "Continuous can be requested without schedule-stop enforcement; backend start guards still apply.",
            "detail": detail,
        }
    if actual_mode != "continuous":
        return {
            "key": SCHEDULE_CONTINUOUS_WATCHER_CHECK_KEY,
            "label": SCHEDULE_CONTINUOUS_WATCHER_LABEL,
            "status": "ready",
            "evidence": f"actual_mode={actual_mode}; watcher not required.",
            "action": "The request resolves away from continuous mode, so no continuous schedule-stop watcher is needed.",
            "detail": detail,
        }
    if override == "ignore":
        return {
            "key": SCHEDULE_CONTINUOUS_WATCHER_CHECK_KEY,
            "label": SCHEDULE_CONTINUOUS_WATCHER_LABEL,
            "status": "high review",
            "evidence": f"override=ignore; backend watcher not owned; next schedule stop={next_stop}.",
            "action": "Use Ignore Schedule only when deliberately bypassing the stop-at-window-end safety net; use V5 for scheduled continuous runs that must stop automatically.",
            "detail": detail,
        }
    if backend_watcher_available:
        if next_stop == "none":
            return {
                "key": SCHEDULE_CONTINUOUS_WATCHER_CHECK_KEY,
                "label": SCHEDULE_CONTINUOUS_WATCHER_LABEL,
                "status": "ready",
                "evidence": "backend watcher is available; no current schedule stop boundary is reported.",
                "action": "Continuous can be requested; if the weekly grid has no transition, no stop flag will be written.",
                "detail": detail,
            }
        return {
            "key": SCHEDULE_CONTINUOUS_WATCHER_CHECK_KEY,
            "label": SCHEDULE_CONTINUOUS_WATCHER_LABEL,
            "status": "ready",
            "evidence": f"backend watcher available; next schedule stop={next_stop}.",
            "action": "Backend will request Stop After Current at the schedule boundary if the launched process is still running.",
            "detail": detail,
        }
    if allowed_now:
        return {
            "key": SCHEDULE_CONTINUOUS_WATCHER_CHECK_KEY,
            "label": SCHEDULE_CONTINUOUS_WATCHER_LABEL,
            "status": "blocked",
            "evidence": f"inside schedule window; backend watcher not owned; next schedule stop={next_stop}.",
            "action": "Use Run Once from WebView, or use V5 for scheduled Continuous until backend watcher ownership is implemented.",
            "detail": detail,
        }
    return {
        "key": SCHEDULE_CONTINUOUS_WATCHER_CHECK_KEY,
        "label": SCHEDULE_CONTINUOUS_WATCHER_LABEL,
        "status": "review",
        "evidence": f"outside schedule window; schedule gate blocks before watcher can matter; next schedule stop={next_stop}.",
        "action": "Resolve the schedule gate first. Use Run Once Outside Window or Ignore Schedule only as explicit operator choices.",
        "detail": detail,
    }


def resolve_pipeline_start_schedule_gate(
    *,
    mode: str,
    request: Mapping[str, Any],
    enabled: bool,
    evaluation: Mapping[str, Any],
    backend_stop_watcher_available: bool = False,
) -> dict[str, Any]:
    if mode in SCHEDULE_UNWATCHED_MODES:
        return {"ok": True, "mode": mode, "data": {"checked": False, "reason": SCHEDULE_MODE_NOT_SCHEDULED_REASON}}

    data = schedule_gate_data(enabled, evaluation)
    if not enabled:
        return {"ok": True, "mode": mode, "data": data}

    override = normalize_schedule_override(request.get("schedule_override"))
    allowed = bool(evaluation.get("allowed_now", False))
    data["backend_stop_watcher_available"] = bool(backend_stop_watcher_available)

    if mode == "continuous" and allowed and override != "ignore" and not backend_stop_watcher_available:
        return {
            "ok": False,
            "message": SCHEDULE_CONTINUOUS_BLOCK_MESSAGE,
            "severity": "warning",
            "data": data,
        }
    if allowed:
        return {"ok": True, "mode": mode, "data": data}

    if override == "run_once":
        data["override"] = override
        return {"ok": True, "mode": "once", "data": data}
    if override == "ignore":
        data["override"] = override
        return {"ok": True, "mode": mode, "data": data}

    return {
        "ok": False,
        "message": SCHEDULE_OUTSIDE_WINDOW_MESSAGE,
        "severity": "warning",
        "data": data,
    }


__all__ = [
    "SCHEDULE_UNWATCHED_MODES",
    "SCHEDULE_MODE_NOT_SCHEDULED_REASON",
    "SCHEDULE_CONTINUOUS_BLOCK_MESSAGE",
    "SCHEDULE_OUTSIDE_WINDOW_MESSAGE",
    "SCHEDULE_CONTINUOUS_WATCHER_CHECK_KEY",
    "SCHEDULE_CONTINUOUS_WATCHER_LABEL",
    "normalize_schedule_override",
    "schedule_gate_data",
    "continuous_schedule_stop_watcher_preflight_check",
    "resolve_pipeline_start_schedule_gate",
]
