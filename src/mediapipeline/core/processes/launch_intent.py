"""Shared pipeline launch request normalization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.pipeline_policy import (
    configured_network_role,
    coordinator_also_encode_locally_enabled,
    normalize_pipeline_extra_args,
    normalize_pipeline_start_mode,
    parse_pipeline_sleep_seconds,
    pipeline_extra_args_error,
    pipeline_start_network_mode_label,
)
from mediapipeline.core.processes.source_path_policy import queue_source_file_validation


@dataclass(frozen=True)
class PipelineLaunchIntent:
    config: dict[str, Any]
    mode: str
    sleep_seconds: int | None
    sleep_error: str | None
    extra_args: list[str]
    extra_args_error: str | None
    single_file: str
    single_file_validation: dict[str, Any] | None
    show_config: bool
    show_console: bool
    schedule_override: str
    queue_scope: str
    priority_export_id: str
    network_role: str
    network_mode_label: str

    def normalized_request(self) -> dict[str, Any]:
        validation = self.single_file_validation or {
            "ok": True,
            "status": "ready",
            "message": "single_file not requested; backend launch will use normal queue scope.",
        }
        return {
            "target": "pipeline",
            "mode": self.mode,
            "sleep_seconds": self.sleep_seconds,
            "show_config": self.show_config,
            "show_console": self.show_console,
            "single_file": self.single_file,
            "schedule_override": self.schedule_override,
            "queue_scope": self.queue_scope,
            "priority_export_id": self.priority_export_id,
            "extra_args_present": bool(self.extra_args),
            "allow_extra_args": False,
            "network_role": self.network_role,
            "network_mode_label": self.network_mode_label,
            "single_file_validation": validation,
        }

    def start_single_file(self) -> str:
        if self.single_file_validation and self.single_file_validation.get("ok"):
            return str(self.single_file_validation.get("normalized_path") or self.single_file)
        return self.single_file


def normalize_pipeline_launch_intent(resolved: ResolvedPaths, request: dict[str, Any]) -> PipelineLaunchIntent:
    config = dict(resolved.config_data or {})
    network_role = configured_network_role(config)
    mode = normalize_pipeline_start_mode(request.get("mode"))
    sleep_seconds, sleep_error = parse_pipeline_sleep_seconds(request.get("sleep_seconds"))
    extra_args = normalize_pipeline_extra_args(request.get("extra_args"))
    single_file = str(request.get("single_file") or "").strip()
    queue_scope = str(request.get("queue_scope") or "backend_queue").strip().casefold()
    priority_export_id = str(request.get("priority_export_id") or "").strip()
    single_file_validation = (
        queue_source_file_validation(resolved, single_file, field_name="single_file")
        if single_file
        else None
    )
    return PipelineLaunchIntent(
        config=config,
        mode=mode,
        sleep_seconds=sleep_seconds,
        sleep_error=sleep_error,
        extra_args=extra_args,
        extra_args_error=pipeline_extra_args_error(extra_args, False),
        single_file=single_file,
        single_file_validation=single_file_validation,
        show_config=bool(request.get("show_config", False)),
        show_console=bool(request.get("show_console", False)),
        schedule_override=str(request.get("schedule_override") or "").strip(),
        queue_scope=queue_scope,
        priority_export_id=priority_export_id,
        network_role=network_role,
        network_mode_label=pipeline_start_network_mode_label(
            network_role,
            coordinator_also_encode_locally=coordinator_also_encode_locally_enabled(config),
        ),
    )


__all__ = [
    "PipelineLaunchIntent",
    "normalize_pipeline_launch_intent",
]
