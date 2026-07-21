"""Pipeline launch facade adapter."""

from __future__ import annotations

import inspect
from uuid import uuid4
from typing import Any

from mediapipeline.core.kernel.dto_commands import CommandResult
from mediapipeline.core.schedule.stop_watcher import schedule_stop_deadline_from_gate
from mediapipeline.core.paths.contracts import ResolvedPaths

from mediapipeline.core.processes.pipeline_policy import (
    coordinator_also_encode_locally_enabled,
    is_supported_pipeline_start_mode,
    pipeline_start_active_work_result,
    pipeline_start_autonomy_blocked_result,
    pipeline_start_config_blocked_result,
    pipeline_start_exception_result,
    pipeline_start_extra_args_error_result,
    pipeline_start_network_mode_blocked_result,
    pipeline_start_queue_scope_blocked_result,
    pipeline_start_schedule_gate_result,
    pipeline_start_single_file_blocked_result,
    pipeline_start_sleep_error_result,
    pipeline_start_success_result,
    pipeline_start_unsupported_mode_result,
    network_role_blocks_normal_launch,
)
from mediapipeline.core.config.identity import config_operation_block_data, config_operation_block_message
from mediapipeline.core.processes.launch_intent import normalize_pipeline_launch_intent
from mediapipeline.core.processes.schedule_policy import normalize_schedule_override
from mediapipeline.core.status.run_monitor import (
    seed_starting_run_monitor,
    terminalize_launch_failed_run,
)


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
        config_identity = dict(getattr(resolved, "config_identity", {}) or {})
        if config_identity.get("blocks_operations") is True:
            return pipeline_start_config_blocked_result(
                config_operation_block_message(config_identity, "Pipeline start"),
                config_operation_block_data(config_identity),
            )
        intent = normalize_pipeline_launch_intent(resolved, request)
        if network_role_blocks_normal_launch(intent.network_role):
            return pipeline_start_network_mode_blocked_result(
                intent.network_role,
                coordinator_also_encode_locally=coordinator_also_encode_locally_enabled(intent.config),
            )
        mode = intent.mode
        if not is_supported_pipeline_start_mode(mode):
            return pipeline_start_unsupported_mode_result()
        if intent.sleep_error is not None or intent.sleep_seconds is None:
            return pipeline_start_sleep_error_result()
        if intent.extra_args_error is not None:
            return pipeline_start_extra_args_error_result()
        single_file = intent.single_file
        single_file_validation = intent.single_file_validation
        if single_file_validation is not None:
            if not single_file_validation.get("ok"):
                return pipeline_start_single_file_blocked_result(
                    {
                        "schema_version": "desktop_pipeline_single_file_launch_block.v1",
                        "message": single_file_validation.get("message"),
                        "validation": single_file_validation,
                        "start_route_allowed": False,
                        "safe_next_action": "Choose one existing supported media file under SourceMovies, SourceTV, or enabled LibraryProfiles.",
                    }
                )
            single_file = intent.start_single_file()
        schedule_gate = self._resolve_pipeline_start_schedule_gate(mode, request)
        if not schedule_gate["ok"]:
            return pipeline_start_schedule_gate_result(schedule_gate)
        actual_mode = str(schedule_gate.get("mode") or mode)
        command_id = str(request.get("_command_id") or "")
        requested_run_id = str(request.get("_run_id") or "").strip().casefold()
        run_monitor_launch = actual_mode == "once" and not single_file
        run_id = ""
        if run_monitor_launch:
            run_id = (
                requested_run_id
                if len(requested_run_id) == 32
                and all(character in "0123456789abcdef" for character in requested_run_id)
                else uuid4().hex
            )
            if not command_id:
                command_id = f"pipeline-start-{run_id}"
        launch_lock, lock_message = self._acquire_process_launch_lock(
            "Pipeline start",
            resolved=resolved,
            command_id=command_id,
            resource_claims=[single_file] if single_file else [],
        )
        if lock_message:
            return pipeline_start_active_work_result(lock_message)
        monitor_state_root = None
        run_monitor_preseeded = False
        runtime_process_started = False
        try:
            recovery_request = {**request, **({"_run_id": run_id} if run_id else {})}
            self._set_process_launch_recovery_descriptor(
                launch_lock,
                route="/api/pipeline/start",
                request=recovery_request,
            )
            block_message = self._active_work_block_message(resolved, "Pipeline start")
            if block_message:
                return pipeline_start_active_work_result(block_message)
            expected_queue_plan_fingerprint = ""
            accepted_run_rows: tuple[Any, ...] = ()
            if actual_mode == "once" and not single_file:
                queue_scope_check = self._normal_queue_scope_preflight_check(
                    resolved,
                    retain_accepted_rows=True,
                )
                if str(queue_scope_check.get("status") or "").casefold() != "ready":
                    return pipeline_start_queue_scope_blocked_result(queue_scope_check)
                expected_queue_plan_fingerprint = str(
                    queue_scope_check.get("queue_plan_fingerprint") or ""
                ).strip()
                accepted_run_rows = tuple(queue_scope_check.get("_accepted_run_rows") or ())
            autonomy_method = getattr(self, "_autonomy_health_for_resolved", None)
            if callable(autonomy_method):
                path_health_method = getattr(self, "_launch_path_health_for_resolved", None)
                path_health = path_health_method(resolved) if callable(path_health_method) else None
                autonomy_health = autonomy_method(resolved, path_health=path_health)
                if (
                    actual_mode != "drain_pending_pushes"
                    and str((autonomy_health or {}).get("overall_status") or "").casefold() == "blocked"
                ):
                    return pipeline_start_autonomy_blocked_result(autonomy_health)
            if run_monitor_launch:
                monitor_state_root = getattr(resolved, "state_root", None)
                if monitor_state_root is None and getattr(resolved, "run_monitor_path", None) is not None:
                    monitor_state_root = resolved.run_monitor_path.parent
                if monitor_state_root is None:
                    raise RuntimeError("Run Once monitor state root is unavailable.")
                seed_starting_run_monitor(
                    monitor_state_root,
                    run_id=run_id,
                    command_id=command_id,
                    accepted_queue_fingerprint=expected_queue_plan_fingerprint,
                    accepted_rows=accepted_run_rows,
                )
                run_monitor_preseeded = True
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
            self._prepare_process_launch_lease(launch_lock)
            start_kwargs: dict[str, Any] = {
                "resolved": resolved,
                "mode": actual_mode,
                "show_config": intent.show_config,
                "sleep_seconds": intent.sleep_seconds,
                "extra_args": intent.extra_args,
                "show_console": intent.show_console,
                "single_file": single_file or None,
            }
            starter_parameters = inspect.signature(starter).parameters
            accepts_extra_kwargs = any(
                parameter.kind is inspect.Parameter.VAR_KEYWORD
                for parameter in starter_parameters.values()
            )
            if accepts_extra_kwargs or "expected_queue_plan_fingerprint" in starter_parameters:
                start_kwargs["expected_queue_plan_fingerprint"] = expected_queue_plan_fingerprint
            if accepts_extra_kwargs or "command_id" in starter_parameters:
                start_kwargs["command_id"] = command_id
            if accepts_extra_kwargs or "run_id" in starter_parameters:
                start_kwargs["run_id"] = run_id
            proc = starter(**start_kwargs)
            runtime_process_started = True
            self._transfer_process_launch_lease(launch_lock, proc)
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
            process_started_before_failure = bool(
                getattr(exc, "_mediapipeline_process_started", False)
            )
            cleanup_verified = bool(
                getattr(exc, "_mediapipeline_cleanup_verified", False)
            )
            launch_failure_is_terminal = (
                not runtime_process_started
                and (not process_started_before_failure or cleanup_verified)
            )
            if run_monitor_preseeded and launch_failure_is_terminal and monitor_state_root is not None:
                try:
                    terminalize_launch_failed_run(
                        monitor_state_root,
                        run_id,
                        reason=str(exc),
                    )
                except Exception as terminalize_exc:
                    exc = RuntimeError(
                        f"{exc}; additionally failed to terminalize the accepted Run Monitor: {terminalize_exc}"
                    )
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
            single_file_validation=single_file_validation,
            run_id=run_id,
            accepted_queue_fingerprint=expected_queue_plan_fingerprint,
        )

__all__ = [
    "PipelineLaunchFacadeMixin",
]
