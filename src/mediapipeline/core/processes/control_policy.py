from __future__ import annotations

from typing import Any


PIPELINE_CONTROL_ACTIONS = frozenset({"pause", "stop", "rescan", "kill"})
PIPELINE_CONTROL_ACTION_ERROR = "Action must be pause, stop, rescan, or kill."
PIPELINE_FORCE_STOP_SCOPE = {
    "requested_scope": "related_pipeline_audit_rerun_process_trees",
    "scope_label": "related pipeline, audit, and CSV rerun PowerShell process trees",
    "job_kinds": ["pipeline", "audit", "rerun_csv"],
}


def normalize_pipeline_control_action(value: Any) -> str:
    return str(value or "").strip().casefold().replace("-", "_")


def pipeline_control_command(action: str) -> str:
    return f"pipeline.control.{action or 'unknown'}"


def is_supported_pipeline_control_action(action: str) -> bool:
    return action in PIPELINE_CONTROL_ACTIONS


def pipeline_control_success_data(action: str, flag_path: Any, extra: dict[str, Any] | None = None) -> dict[str, Any]:
    data: dict[str, Any] = {"action": action, "flag_path": str(flag_path or "")}
    if action == "kill":
        data["force_stop_scope"] = dict(PIPELINE_FORCE_STOP_SCOPE)
    if extra:
        data.update(extra)
    return data


__all__ = [
    "PIPELINE_CONTROL_ACTIONS",
    "PIPELINE_CONTROL_ACTION_ERROR",
    "PIPELINE_FORCE_STOP_SCOPE",
    "normalize_pipeline_control_action",
    "pipeline_control_command",
    "is_supported_pipeline_control_action",
    "pipeline_control_success_data",
]
