"""Pipeline launch facade adapter."""

from __future__ import annotations

from typing import Any

from mediapipeline_desktop_app.application.dto_commands import CommandResult
from mediapipeline_desktop_app.application.schedule_stop_watcher import schedule_stop_deadline_from_gate
from mediapipeline_desktop_app.models import ResolvedPaths

from app.processes.pipeline_policy import (
    is_supported_pipeline_start_mode,
    normalize_pipeline_extra_args,
    normalize_pipeline_start_mode,
    parse_pipeline_sleep_seconds,
    pipeline_extra_args_error,
    pipeline_start_active_work_result,
    pipeline_start_exception_result,
    pipeline_start_extra_args_error_result,
    pipeline_start_schedule_gate_result,
    pipeline_start_sleep_error_result,
    pipeline_start_success_result,
    pipeline_start_unsupported_mode_result,
)
from app.processes.schedule_policy import normalize_schedule_override


class PipelineLaunchFacadeMixin:
    """Pipeline start command adapter for the application facade."""

    def _cancel_pipeline_schedule_stop_watcher(self, reason: str) -> None:
        watcher = getattr(self, "_schedule_stop_watcher", None)
        cancel = getattr(watcher, "cancel", None)
        if callable(cancel):
            cancel(reason)

    def _arm_pipeline_schedule_stop_watcher(
        self,
        *,
        resolved: ResolvedPaths,
        proc: object,
        actual_mode: str,
        requested_mode: str,
        request: dict[str, Any],
        schedule_gate: dict[str, Any],
    ) -> list[str]:
        if actual_mode != "continuous" or requested_mode != "continuous":
            return []
        if normalize_schedule_override(request.get("schedule_override")) == "ignore":
            return ["Schedule-stop watcher not armed because Ignore Schedule was selected."]
        data = schedule_gate.get("data") if isinstance(schedule_gate.get("data"), dict) else {}
        if not bool(data.get("enabled", False)):
            return ["Schedule-stop watcher not armed because schedule enforcement is off."]
        deadline = schedule_stop_deadline_from_gate(schedule_gate)
        if deadline is None:
            return ["Schedule-stop watcher not armed because the current schedule has no stop boundary."]
        watcher = getattr(self, "_schedule_stop_watcher", None)
        arm = getattr(watcher, "arm", None)
        if not callable(arm):
            return ["Schedule-stop watcher unavailable; no backend stop-at-window-end guard was armed."]
        state = arm(service=self.service, resolved=resolved, proc=proc, deadline=deadline)
        message = str(getattr(state, "message", "") or "")
        return [message] if message else []

    def start_pipeline_process(self, resolved: ResolvedPaths, request: dict[str, Any]) -> CommandResult:
        mode = normalize_pipeline_start_mode(request.get("mode"))
        if not is_supported_pipeline_start_mode(mode):
            return pipeline_start_unsupported_mode_result()
        sleep_seconds, sleep_error = parse_pipeline_sleep_seconds(request.get("sleep_seconds"))
        if sleep_error is not None or sleep_seconds is None:
            return pipeline_start_sleep_error_result()
        extra_args = normalize_pipeline_extra_args(request.get("extra_args"))
        extra_args_error = pipeline_extra_args_error(extra_args, False)
        if extra_args_error is not None:
            return pipeline_start_extra_args_error_result()
        schedule_gate = self._resolve_pipeline_start_schedule_gate(mode, request)
        if not schedule_gate["ok"]:
            return pipeline_start_schedule_gate_result(schedule_gate)
        actual_mode = str(schedule_gate.get("mode") or mode)
        launch_lock, lock_message = self._acquire_process_launch_lock("Pipeline start")
        if lock_message:
            return pipeline_start_active_work_result(lock_message)
        try:
            block_message = self._active_work_block_message(resolved, "Pipeline start")
            if block_message:
                return pipeline_start_active_work_result(block_message)
            self._cancel_pipeline_schedule_stop_watcher("cleared before a new backend pipeline launch")
            launch_prep_messages: list[str] = []
            runtime_prep = getattr(self.service, "prepare_pipeline_runtime_for_launch", None)
            if callable(runtime_prep):
                launch_prep_messages.extend(str(item) for item in runtime_prep(resolved))
            control_prep = getattr(self.service, "prepare_pipeline_control_flags_for_launch", None)
            if callable(control_prep):
                launch_prep_messages.extend(str(item) for item in control_prep(resolved))
            starter = getattr(self.service, "start_pipeline", None)
            if not callable(starter):
                raise RuntimeError("Pipeline start service is not available.")
            proc = starter(
                resolved=resolved,
                mode=actual_mode,
                show_config=bool(request.get("show_config", False)),
                sleep_seconds=sleep_seconds,
                extra_args=extra_args,
                show_console=bool(request.get("show_console", False)),
                single_file=str(request.get("single_file") or "").strip() or None,
            )
            pid = int(getattr(proc, "pid", 0) or 0)
            launch_prep_messages.extend(
                self._arm_pipeline_schedule_stop_watcher(
                    resolved=resolved,
                    proc=proc,
                    actual_mode=actual_mode,
                    requested_mode=mode,
                    request=request,
                    schedule_gate=schedule_gate,
                )
            )
            launch_logs = ""
            log_method = getattr(self.service, "launch_log_summary", None)
            if callable(log_method):
                launch_logs = str(log_method() or "")
        except Exception as exc:
            return pipeline_start_exception_result(exc)
        finally:
            self._release_process_launch_lock(launch_lock)
        return pipeline_start_success_result(
            actual_mode=actual_mode,
            requested_mode=mode,
            schedule_data=schedule_gate.get("data") or {},
            pid=pid,
            launch_prep_messages=launch_prep_messages,
            launch_logs=launch_logs,
        )

__all__ = [
    "PipelineLaunchFacadeMixin",
]
