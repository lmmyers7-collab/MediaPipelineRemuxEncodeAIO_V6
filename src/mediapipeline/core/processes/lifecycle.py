from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Any

try:
    import psutil
except Exception:  # pragma: no cover - optional runtime dependency
    psutil = None

from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.core.processes.constants import (
    ACTIVE_JOB_STALE_VALIDATE_HEARTBEAT_SECONDS,
    AUDIT_PROGRESS_LAUNCH_CLEANUP_STALE_SECONDS,
    CONTROL_FLAG_STALE_AFTER_SECONDS,
    PIPELINE_PROGRESS_LAUNCH_CLEANUP_STALE_SECONDS,
    PROCESS_LAUNCH_READY_CHECK_SECONDS,
)
from .active_job_runner import (
    active_job_close_block_messages_for_service,
    active_job_pid_is_alive_for_service,
    active_job_record_path_for_proc_for_service,
    active_jobs_dir_for_service,
    cleanup_stale_launch_guards_for_service,
    reconcile_active_job_records_for_service,
    update_active_job_record_for_service,
    write_active_job_launch_record_for_service,
    write_active_job_payload_for_service,
)
from .control_runner import (
    control_flag_age_seconds_for_service,
    new_control_flag_payload_for_service,
    prepare_pipeline_control_flags_for_service,
    read_control_flag_payload_for_service,
    remove_control_flag_for_service,
    toggle_pause_flag_for_service,
    write_control_flag_for_service,
    write_flag_for_service,
)
from .launch_env import build_launch_environment, iter_bundled_launch_dirs
from .launch_runner import (
    start_audit_for_service,
    start_pipeline_for_service,
    start_rerun_csv_for_service,
)
from .kill import (
    fallback_kill_process_handle,
    find_related_pipeline_processes,
    kill_process_tree,
    kill_psutil_process_tree,
    kill_related_pipeline_processes,
    process_text_contains_any,
    wait_for_process_exit,
)
from .logs import launch_log_summary, launch_log_tail_summary, spawn_log_tail
from .readiness import verify_spawn_readiness
from .runtime_runner import (
    clear_audit_progress_artifacts_for_service,
    clear_pipeline_progress_artifacts_for_service,
    clear_runtime_artifacts_for_service,
    prepare_audit_runtime_for_service,
    prepare_pipeline_runtime_for_service,
    runtime_artifact_specs_for_service,
    runtime_state_root_for_service,
    validate_runtime_artifact_target_for_service,
)
from .spawn_runner import spawn_process_for_service


class ProcessLifecycleServiceMixin:
    def _iter_bundled_launch_dirs(self) -> list[Path]:
        return iter_bundled_launch_dirs(self.app_root, self.workspace_root)

    def _build_launch_environment(self) -> dict[str, str]:
        return build_launch_environment(self.app_root, self.workspace_root)

    def start_pipeline(
        self,
        resolved: ResolvedPaths,
        mode: str,
        show_config: bool,
        sleep_seconds: int,
        extra_args: str,
        show_console: bool,
        single_file: str | None = None,
        extra_argv: list[str] | tuple[str, ...] | None = None,
    ) -> subprocess.Popen[Any]:
        return start_pipeline_for_service(
            self,
            resolved,
            mode=mode,
            show_config=show_config,
            sleep_seconds=sleep_seconds,
            extra_args=extra_args,
            extra_argv=extra_argv,
            show_console=show_console,
            single_file=single_file,
        )

    def start_audit(
        self,
        resolved: ResolvedPaths,
        library_root: str,
        include_sidecars: bool,
        show_console: bool,
    ) -> subprocess.Popen[Any]:
        return start_audit_for_service(
            self,
            resolved,
            library_root=library_root,
            include_sidecars=include_sidecars,
            show_console=show_console,
        )

    def start_rerun_csv(
        self,
        resolved: ResolvedPaths,
        csv_path: Path,
        *,
        dry_run: bool,
        stage_mode: str,
        original_mode: str,
        return_mode: str,
        show_console: bool,
        plan_only: bool = False,
    ) -> subprocess.Popen[Any]:
        return start_rerun_csv_for_service(
            self,
            resolved,
            csv_path,
            dry_run=dry_run,
            plan_only=plan_only,
            stage_mode=stage_mode,
            original_mode=original_mode,
            return_mode=return_mode,
            show_console=show_console,
        )

    def _spawn(
        self,
        args: list[str],
        show_console: bool,
        *,
        resolved: ResolvedPaths | None = None,
        job_kind: str = "process",
        mode: str = "",
        metadata: dict[str, Any] | None = None,
    ) -> subprocess.Popen[Any]:
        return spawn_process_for_service(
            self,
            args,
            show_console,
            resolved=resolved,
            job_kind=job_kind,
            mode=mode,
            metadata=metadata,
        )

    def _register_active_spawned_process(self, proc: subprocess.Popen[Any], job_kind: str) -> None:
        pid = int(getattr(proc, "pid", 0) or 0)
        if pid <= 0:
            return
        lock = getattr(self, "_active_spawned_processes_lock", None)
        active = getattr(self, "_active_spawned_processes", None)
        if lock is None or not isinstance(active, dict):
            return
        with lock:
            active[pid] = (proc, str(job_kind or "process"))

    def _unregister_active_spawned_process(self, proc: subprocess.Popen[Any]) -> bool:
        pid = int(getattr(proc, "pid", 0) or 0)
        if pid <= 0:
            return False
        lock = getattr(self, "_active_spawned_processes_lock", None)
        active = getattr(self, "_active_spawned_processes", None)
        if lock is None or not isinstance(active, dict):
            return False
        with lock:
            return active.pop(pid, None) is not None

    def _active_spawned_process_is_registered(self, proc: subprocess.Popen[Any]) -> bool:
        pid = int(getattr(proc, "pid", 0) or 0)
        if pid <= 0:
            return False
        lock = getattr(self, "_active_spawned_processes_lock", None)
        active = getattr(self, "_active_spawned_processes", None)
        if lock is None or not isinstance(active, dict):
            return False
        with lock:
            return pid in active

    def kill_active_spawned_processes(self) -> list[str]:
        lock = getattr(self, "_active_spawned_processes_lock", None)
        active = getattr(self, "_active_spawned_processes", None)
        if lock is None or not isinstance(active, dict):
            return []
        with lock:
            items = list(active.items())
        messages: list[str] = []
        for _pid, (proc, job_kind) in items:
            poll = getattr(proc, "poll", None)
            return_code = poll() if callable(poll) else None
            was_registered = self._unregister_active_spawned_process(proc)
            try:
                if return_code is None:
                    messages.append(self.kill_process_tree(proc, job_kind))
                else:
                    self.update_active_job_record(proc, return_code=return_code)
            except Exception:
                if was_registered:
                    self._register_active_spawned_process(proc, job_kind)
                raise
        return messages

    def _active_jobs_dir_for_resolved(self, resolved: ResolvedPaths | None) -> Path | None:
        return active_jobs_dir_for_service(self, resolved)

    def _active_job_record_path_for_proc(self, proc: subprocess.Popen[Any] | None) -> Path | None:
        return active_job_record_path_for_proc_for_service(self, proc)

    def _write_active_job_payload(self, record_path: Path, payload: dict[str, Any]) -> None:
        write_active_job_payload_for_service(self, record_path, payload)

    def _write_active_job_launch_record(
        self,
        proc: subprocess.Popen[Any],
        *,
        resolved: ResolvedPaths | None,
        job_kind: str,
        mode: str,
        command_line: str,
        args: list[str],
        launch_cwd: Path,
        show_console: bool,
        metadata: dict[str, Any],
    ) -> Path | None:
        return write_active_job_launch_record_for_service(
            self,
            proc,
            resolved=resolved,
            job_kind=job_kind,
            mode=mode,
            command_line=command_line,
            args=args,
            launch_cwd=launch_cwd,
            show_console=show_console,
            metadata=metadata,
        )

    def _active_job_pid_is_alive(self, pid: int) -> bool | None:
        return active_job_pid_is_alive_for_service(self, pid, psutil)

    def active_job_close_block_messages(
        self,
        resolved: ResolvedPaths,
        *,
        max_items: int = 24,
        job_kinds: set[str] | None = None,
    ) -> list[str]:
        return active_job_close_block_messages_for_service(
            self,
            resolved,
            max_items=max_items,
            psutil_module=psutil,
            job_kinds=job_kinds,
        )

    def reconcile_active_job_records(self, resolved: ResolvedPaths, *, max_items: int = 24) -> list[str]:
        return reconcile_active_job_records_for_service(self, resolved, max_items=max_items, psutil_module=psutil)

    def cleanup_stale_launch_guards(
        self,
        resolved: ResolvedPaths,
        *,
        max_items: int = 24,
        stale_after_seconds: float = ACTIVE_JOB_STALE_VALIDATE_HEARTBEAT_SECONDS,
    ) -> list[str]:
        return cleanup_stale_launch_guards_for_service(
            self,
            resolved,
            max_items=max_items,
            stale_after_seconds=stale_after_seconds,
            psutil_module=psutil,
        )

    def update_active_job_record(
        self,
        proc: subprocess.Popen[Any] | None,
        *,
        status: str | None = None,
        return_code: int | None = None,
    ) -> None:
        update_active_job_record_for_service(self, proc, status=status, return_code=return_code)

    def _spawn_log_tail(self, path: Path | None) -> str:
        return spawn_log_tail(path)

    def _verify_spawn_readiness(self, proc: subprocess.Popen[Any], command_line: str) -> None:
        verify_spawn_readiness(
            proc,
            command_line,
            ready_check_seconds=PROCESS_LAUNCH_READY_CHECK_SECONDS,
            update_active_job_record=self.update_active_job_record,
            launch_log_summary=self.launch_log_summary,
            spawn_log_tail=self._spawn_log_tail,
            stdout_log=self._last_spawn_stdout_log,
            stderr_log=self._last_spawn_stderr_log,
            logger=self.logger,
        )

    def launch_log_summary(self) -> str:
        return launch_log_summary(self._last_spawn_stdout_log, self._last_spawn_stderr_log)

    def launch_log_tail_summary(self, line_count: int = 12) -> str:
        return launch_log_tail_summary(self._last_spawn_stdout_log, self._last_spawn_stderr_log, line_count=line_count)

    def _wait_for_process_exit(self, proc: subprocess.Popen[Any], timeout_seconds: float = 5.0) -> bool:
        return wait_for_process_exit(proc, timeout_seconds=timeout_seconds)

    def _fallback_kill_process_handle(self, proc: subprocess.Popen[Any], label: str) -> None:
        fallback_kill_process_handle(proc, label, logger=self.logger)

    def _kill_psutil_process_tree(self, process: Any, label: str, timeout_seconds: float = 5.0) -> None:
        kill_psutil_process_tree(process, label, psutil_module=psutil, logger=self.logger, timeout_seconds=timeout_seconds)

    def _process_text_contains_any(self, proc: Any, needles: list[str]) -> bool:
        return process_text_contains_any(proc, needles)

    def find_related_pipeline_processes(
        self,
        resolved: ResolvedPaths,
        *,
        job_kinds: set[str] | None = None,
    ) -> list[Any]:
        return find_related_pipeline_processes(
            resolved,
            psutil_module=psutil,
            current_pid=os.getpid(),
            job_kinds=job_kinds,
        )

    def kill_related_pipeline_processes(self, resolved: ResolvedPaths) -> list[str]:
        return kill_related_pipeline_processes(resolved, psutil_module=psutil, logger=self.logger)

    def kill_process_tree(self, proc: subprocess.Popen[Any] | None, label: str) -> str:
        return kill_process_tree(
            proc,
            label,
            psutil_module=psutil,
            logger=self.logger,
            update_active_job_record=self.update_active_job_record,
        )

    def _runtime_state_root_for_resolved(self, resolved: ResolvedPaths) -> Path | None:
        return runtime_state_root_for_service(self, resolved)

    def _runtime_artifact_specs(
        self,
        resolved: ResolvedPaths,
        *,
        include_pipeline: bool,
        include_audit: bool,
    ) -> list[tuple[str, Path | None, list[Path]]]:
        return runtime_artifact_specs_for_service(
            self,
            resolved,
            include_pipeline=include_pipeline,
            include_audit=include_audit,
        )

    def _validate_runtime_artifact_target(self, label: str, path: Path, expected_paths: list[Path]) -> None:
        validate_runtime_artifact_target_for_service(self, label, path, expected_paths)

    def clear_runtime_artifacts(
        self,
        resolved: ResolvedPaths,
        *,
        include_pipeline: bool,
        include_audit: bool,
    ) -> list[str]:
        return clear_runtime_artifacts_for_service(
            self,
            resolved,
            include_pipeline=include_pipeline,
            include_audit=include_audit,
        )

    def _clear_pipeline_progress_artifacts(self, resolved: ResolvedPaths) -> list[str]:
        return clear_pipeline_progress_artifacts_for_service(self, resolved)

    def prepare_pipeline_runtime_for_launch(
        self,
        resolved: ResolvedPaths,
        *,
        stale_after_seconds: float = PIPELINE_PROGRESS_LAUNCH_CLEANUP_STALE_SECONDS,
    ) -> list[str]:
        return prepare_pipeline_runtime_for_service(self, resolved, stale_after_seconds=stale_after_seconds)

    def _clear_audit_progress_artifacts(self, resolved: ResolvedPaths) -> list[str]:
        return clear_audit_progress_artifacts_for_service(self, resolved)

    def prepare_audit_runtime_for_launch(
        self,
        resolved: ResolvedPaths,
        *,
        stale_after_seconds: float = AUDIT_PROGRESS_LAUNCH_CLEANUP_STALE_SECONDS,
    ) -> list[str]:
        return prepare_audit_runtime_for_service(self, resolved, stale_after_seconds=stale_after_seconds)

    def _new_control_flag_payload(self, label: str) -> dict[str, Any]:
        return new_control_flag_payload_for_service(self, label)

    def _write_control_flag(self, flag_path: Path, label: str) -> dict[str, Any]:
        return write_control_flag_for_service(self, flag_path, label)

    def _remove_control_flag(self, flag_path: Path, label: str) -> None:
        remove_control_flag_for_service(self, flag_path, label)

    def _read_control_flag_payload(self, flag_path: Path) -> dict[str, Any] | None:
        return read_control_flag_payload_for_service(self, flag_path)

    def _control_flag_age_seconds(self, flag_path: Path, payload: dict[str, Any] | None) -> float | None:
        return control_flag_age_seconds_for_service(self, flag_path, payload)

    def prepare_pipeline_control_flags_for_launch(
        self,
        resolved: ResolvedPaths,
        *,
        stale_after_seconds: float = CONTROL_FLAG_STALE_AFTER_SECONDS,
    ) -> list[str]:
        return prepare_pipeline_control_flags_for_service(self, resolved, stale_after_seconds=stale_after_seconds)

    def toggle_pause_flag(self, resolved: ResolvedPaths) -> str:
        return toggle_pause_flag_for_service(self, resolved)

    def write_flag(self, flag_path: Path | None, label: str) -> str:
        return write_flag_for_service(self, flag_path, label)
