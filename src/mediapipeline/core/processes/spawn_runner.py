from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import subprocess
import threading
import time
from typing import Any, Protocol, cast
from collections.abc import Mapping

from mediapipeline.core.paths.contracts import ResolvedPaths
from mediapipeline.core.processes.constants import ACTIVE_JOB_HEARTBEAT_SECONDS
from mediapipeline.core.processes.kill import (
    _mark_process_tree_cleanup_reconciliation_required,
    _process_tree_cleanup_attempt_in_progress,
    _process_tree_cleanup_reconciliation_required,
    _process_tree_cleanup_terminal_evidence,
    _wait_for_process_tree_cleanup_attempt,
)
from mediapipeline.core.processes.rerun_lifecycle import finalize_rerun_enrollment_after_exit

from .spawn import (
    build_spawn_command_line,
    build_spawn_kwargs,
    build_spawn_log_paths,
    hidden_creationflags,
    launch_cwd_for_roots,
)


_launch_cleanup_reconciliation_lock = threading.Lock()
_launch_cleanup_reconciliation_leases: dict[int, object] = {}


def _mark_launch_cleanup_reconciliation_required(lease: object) -> None:
    with _launch_cleanup_reconciliation_lock:
        _launch_cleanup_reconciliation_leases[id(lease)] = lease


def _launch_cleanup_reconciliation_required(lease: object) -> bool:
    """Peek at ambiguous launch cleanup without consuming guard ownership."""

    with _launch_cleanup_reconciliation_lock:
        return _launch_cleanup_reconciliation_leases.get(id(lease)) is lease


def _consume_launch_cleanup_reconciliation_required(lease: object) -> bool:
    with _launch_cleanup_reconciliation_lock:
        marked_lease = _launch_cleanup_reconciliation_leases.get(id(lease))
        if marked_lease is not lease:
            return False
        del _launch_cleanup_reconciliation_leases[id(lease)]
        return True


class InfoWarningLogger(Protocol):
    def info(self, message: object, *args: object, **kwargs: object) -> None: ...

    def warning(self, message: object, *args: object, **kwargs: object) -> None: ...


class ProcessSpawnService(Protocol):
    app_root: Path
    workspace_root: Path
    run_logs_root: Path
    logger: InfoWarningLogger
    _last_spawn_stdout_log: Path | None
    _last_spawn_stderr_log: Path | None

    def _build_launch_environment(self) -> Mapping[str, str]: ...

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
    ) -> Path | None: ...

    def _verify_spawn_readiness(self, proc: subprocess.Popen[Any], command_line: str) -> None: ...


@dataclass
class _ProcessOwnershipFinalizationContext:
    service: ProcessSpawnService
    proc_identity: int
    job_kind: str
    resolved: ResolvedPaths | None
    metadata: dict[str, Any]
    lock: threading.RLock = field(default_factory=threading.RLock)
    launch_failed: bool = False
    terminal_evidence_recorded: bool = False
    lease_released: bool = False
    finalized: bool = False


def _process_ownership_finalization_context(
    proc: object,
) -> _ProcessOwnershipFinalizationContext | None:
    context = getattr(proc, "_mediapipeline_ownership_finalization_context", None)
    if isinstance(context, _ProcessOwnershipFinalizationContext) and context.proc_identity == id(proc):
        return context
    return None


def _ensure_process_ownership_finalization_context(
    service: ProcessSpawnService,
    proc: object,
    job_kind: str,
    *,
    resolved: ResolvedPaths | None,
    metadata: Mapping[str, Any] | None,
) -> _ProcessOwnershipFinalizationContext:
    existing = _process_ownership_finalization_context(proc)
    if existing is not None:
        with existing.lock:
            existing.resolved = resolved if resolved is not None else existing.resolved
            existing.metadata.update(dict(metadata or {}))
        return existing
    context = _ProcessOwnershipFinalizationContext(
        service=service,
        proc_identity=id(proc),
        job_kind=str(job_kind or "process"),
        resolved=resolved,
        metadata=dict(metadata or {}),
    )
    cast(Any, proc)._mediapipeline_ownership_finalization_context = context
    return context


def _mark_process_ownership_launch_failed(proc: object) -> None:
    context = _process_ownership_finalization_context(proc)
    if context is not None:
        with context.lock:
            context.launch_failed = True


def _finalize_process_ownership_after_tree_proof(
    proc: object,
    return_code: int | None,
) -> bool:
    """Finalize exact process ownership once, and only after tree cleanup proof."""

    if _process_tree_cleanup_attempt_in_progress(proc) or _process_tree_cleanup_reconciliation_required(proc):
        return False
    context = _process_ownership_finalization_context(proc)
    if context is None:
        return False
    with context.lock:
        if context.finalized:
            return False
        service = context.service
        evidence = _process_tree_cleanup_terminal_evidence(proc)
        update_active_job = getattr(service, "update_active_job_record", None)
        is_registered = getattr(service, "_active_spawned_process_is_registered", None)
        exact_owner_registered = True
        if callable(is_registered):
            try:
                exact_owner_registered = bool(is_registered(proc))
            except Exception as exc:
                exact_owner_registered = False
                service.logger.warning(
                    "Could not verify exact %s process ownership before finalization: %s",
                    context.job_kind,
                    exc,
                )
        active_job_updated = False
        if callable(update_active_job) and exact_owner_registered:
            try:
                if evidence is not None and evidence.status == "killed" and evidence.active_job_write_succeeded:
                    active_job_updated = True
                elif evidence is not None and evidence.status in {"killed", "kill_degraded"}:
                    update_active_job(proc, status="killed", return_code=return_code)
                    active_job_updated = True
                else:
                    update_active_job(proc, return_code=return_code)
                    active_job_updated = True
            except Exception as exc:
                service.logger.warning(
                    "Process-tree exit was proven for %s, but terminal ActiveJobs evidence could not be written: %s",
                    context.job_kind,
                    exc,
                )
        if context.job_kind == "rerun_csv":
            try:
                finalize_rerun_enrollment_after_exit(dict(context.metadata), return_code)
            except Exception as exc:
                service.logger.warning(
                    "Failed to finalize %s enrollment after proven process-tree exit: %s",
                    context.job_kind,
                    exc,
                )
        if active_job_updated:
            sync_after_exit = getattr(service, "sync_audit_sources_after_process_exit", None)
            if callable(sync_after_exit):
                try:
                    sync_after_exit(
                        proc,
                        resolved=context.resolved,
                        job_kind=context.job_kind,
                        return_code=return_code,
                        metadata=dict(context.metadata),
                    )
                except Exception as exc:
                    service.logger.warning("Failed to sync %s post-exit state: %s", context.job_kind, exc)

        command_id = str(context.metadata.get("command_id") or "").strip()
        record_terminal_evidence = getattr(service, "record_process_terminal_command_evidence", None)
        if command_id and context.job_kind == "pipeline" and not context.terminal_evidence_recorded:
            if callable(record_terminal_evidence):
                terminal_phase = (
                    "interrupted"
                    if evidence is not None and evidence.status in {"killed", "kill_degraded"}
                    else ("completed" if return_code == 0 and not context.launch_failed else "failed")
                )
                try:
                    record_terminal_evidence(
                        command_id=command_id,
                        phase=terminal_phase,
                        return_code=return_code,
                        pid=int(getattr(proc, "pid", 0) or 0),
                        mode=str(context.metadata.get("mode") or ""),
                    )
                    context.terminal_evidence_recorded = True
                except Exception as exc:
                    service.logger.warning(
                        "Terminal command evidence for %s could not be persisted; lifecycle ownership was preserved: %s",
                        context.job_kind,
                        exc,
                    )
                    return False
            else:
                context.terminal_evidence_recorded = True

        lease = getattr(proc, "_mediapipeline_lifecycle_lease", None)
        release = getattr(lease, "release", None)
        if callable(release) and not context.lease_released:
            try:
                release(
                    outcome=(
                        "launch_failed"
                        if context.launch_failed
                        else ("completed" if return_code == 0 else "failed")
                    )
                )
                context.lease_released = True
            except Exception as exc:
                service.logger.warning(
                    "Failed to release %s lifecycle lease after proven process-tree exit: %s",
                    context.job_kind,
                    exc,
                )
                return False
        else:
            context.lease_released = True

        unregister = getattr(service, "_unregister_active_spawned_process", None)
        if callable(unregister):
            try:
                unregister(proc)
            except Exception as exc:
                service.logger.warning(
                    "Failed to unregister %s after proven process-tree exit: %s",
                    context.job_kind,
                    exc,
                )
                return False
        if callable(is_registered):
            try:
                if is_registered(proc):
                    service.logger.warning(
                        "Exact %s process ownership remained registered after proven process-tree exit.",
                        context.job_kind,
                    )
                    return False
            except Exception as exc:
                service.logger.warning(
                    "Could not verify %s process ownership was unregistered: %s",
                    context.job_kind,
                    exc,
                )
                return False
        context.finalized = True
        return True


def _stop_started_process_after_launch_failure(
    service: ProcessSpawnService,
    proc: subprocess.Popen[Any],
    job_kind: str,
) -> str | None:
    if proc.poll() is not None:
        return None
    label = f"{job_kind} launch failure"
    kill_tree = getattr(service, "kill_process_tree", None)
    kill_detail = ""
    fallback_error = ""
    tree_cleanup_unverified = not callable(kill_tree)
    try:
        if callable(kill_tree):
            kill_detail = str(kill_tree(proc, label) or "")
            normalized_kill_detail = kill_detail.casefold()
            tree_cleanup_unverified = not kill_detail.strip() or any(
                marker in normalized_kill_detail
                for marker in (
                    "could not be verified",
                    "unable to verify",
                    "kill_degraded",
                    "timed out",
                    "degraded",
                    "failed to stop",
                    "failed to kill",
                    "kill failed",
                    "termination failed",
                    "reported a failure",
                    "already exited",
                )
            )
    except Exception as exc:
        kill_detail = f"process-tree termination raised {type(exc).__name__}: {exc}"
        tree_cleanup_unverified = True
    if tree_cleanup_unverified:
        _mark_process_tree_cleanup_reconciliation_required(proc)
    if proc.poll() is None:
        try:
            proc.kill()
            proc.wait(timeout=5.0)
        except Exception as exc:
            fallback_error = f"direct termination fallback raised {type(exc).__name__}: {exc}"
    root_exit_verified = proc.poll() is not None
    if root_exit_verified and not tree_cleanup_unverified:
        return None
    details = "; ".join(detail for detail in (kill_detail, fallback_error) if detail)
    if tree_cleanup_unverified:
        message = f"Could not verify that the {job_kind} process tree exited after launch failure."
        if root_exit_verified:
            message = f"{message} The root process exited, but descendant cleanup evidence remained degraded."
    else:
        message = f"Could not verify that the {job_kind} process exited after launch failure."
    if details:
        message = f"{message} {details}"
    service.logger.warning("%s", message)
    return message


def _start_active_job_completion_watcher(
    service: ProcessSpawnService,
    proc: subprocess.Popen[Any],
    job_kind: str,
    *,
    resolved: ResolvedPaths | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> bool:
    update_active_job = getattr(service, "update_active_job_record", None)
    wait_for_exit = getattr(proc, "wait", None)
    if not callable(update_active_job) or not callable(wait_for_exit):
        return False
    _ensure_process_ownership_finalization_context(
        service,
        proc,
        job_kind,
        resolved=resolved,
        metadata=metadata,
    )

    def _watch() -> None:
        try:
            return_code = wait_for_exit()
        except Exception as exc:
            poll = getattr(proc, "poll", None)
            try:
                polled_return_code = poll() if callable(poll) else None
            except Exception:
                polled_return_code = None
            if polled_return_code is not None:
                return_code = polled_return_code
                service.logger.warning(
                    "Failed to wait for %s process exit, but poll verified terminal return code %s: %s",
                    job_kind,
                    return_code,
                    exc,
                )
            else:
                service.logger.warning(
                    "Failed to observe %s process exit; registration and lifecycle lease were preserved because "
                    "reconciliation is required: %s",
                    job_kind,
                    exc,
                )
                return
        if not _wait_for_process_tree_cleanup_attempt(proc):
            service.logger.warning(
                "Preserved %s ownership because process-tree cleanup did not quiesce within the bounded wait.",
                job_kind,
            )
            return
        if _process_tree_cleanup_reconciliation_required(proc):
            service.logger.warning(
                "Preserved %s ActiveJobs, enrollment, process registration, and lifecycle lease after root exit "
                "because process-tree cleanup requires reconciliation.",
                job_kind,
            )
            return
        _finalize_process_ownership_after_tree_proof(proc, return_code)

    watcher = threading.Thread(
        target=_watch,
        name=f"mediapipeline-{job_kind}-active-job-completion",
        daemon=True,
    )
    watcher.start()
    return True


def _start_active_job_heartbeat_watcher(
    service: ProcessSpawnService,
    proc: subprocess.Popen[Any],
    job_kind: str,
    *,
    interval_seconds: float = ACTIVE_JOB_HEARTBEAT_SECONDS,
) -> bool:
    update_active_job = getattr(service, "update_active_job_record", None)
    poll = getattr(proc, "poll", None)
    if not callable(update_active_job) or not callable(poll):
        return False
    is_active_process_registered = getattr(service, "_active_spawned_process_is_registered", None)

    def _heartbeat() -> None:
        while True:
            time.sleep(max(1.0, float(interval_seconds)))
            if callable(is_active_process_registered) and not is_active_process_registered(proc):
                return
            if _process_tree_cleanup_attempt_in_progress(proc):
                return
            if _process_tree_cleanup_reconciliation_required(proc):
                return
            try:
                if poll() is not None:
                    return
                update_active_job(proc, status="active", return_code=None)
                lease = getattr(proc, "_mediapipeline_lifecycle_lease", None)
                heartbeat = getattr(lease, "heartbeat", None)
                if callable(heartbeat):
                    heartbeat()
            except Exception as exc:
                service.logger.warning("Failed to heartbeat %s ActiveJobs record: %s", job_kind, exc)

    watcher = threading.Thread(
        target=_heartbeat,
        name=f"mediapipeline-{job_kind}-active-job-heartbeat",
        daemon=True,
    )
    watcher.start()
    return True


def spawn_process_for_service(
    service: ProcessSpawnService,
    args: list[str],
    show_console: bool,
    *,
    resolved: ResolvedPaths | None = None,
    job_kind: str = "process",
    mode: str = "",
    metadata: dict[str, Any] | None = None,
) -> subprocess.Popen[Any]:
    creationflags = hidden_creationflags(show_console)
    command_line = build_spawn_command_line(args)
    service.logger.info("Launching: %s", command_line)
    log_paths = build_spawn_log_paths(
        service.app_root,
        run_logs_root=getattr(service, "run_logs_root", None),
    )
    stdout_log = log_paths.stdout_log
    stderr_log = log_paths.stderr_log
    stdout_handle = stdout_log.open("ab")
    stderr_handle = stderr_log.open("ab")
    service._last_spawn_stdout_log = stdout_log
    service._last_spawn_stderr_log = stderr_log
    launch_cwd = launch_cwd_for_roots(service.app_root, service.workspace_root)
    kwargs = build_spawn_kwargs(
        launch_cwd=launch_cwd,
        environment=dict(service._build_launch_environment()),
        stdout_handle=stdout_handle,
        stderr_handle=stderr_handle,
        creationflags=creationflags,
    )
    try:
        proc = subprocess.Popen(args, stdin=subprocess.DEVNULL, **kwargs)
        watcher_metadata = dict(metadata or {})
        if job_kind == "rerun_csv":
            watcher_metadata.update(
                {
                    "stdout_log": str(stdout_log),
                    "stderr_log": str(stderr_log),
                }
            )
        _ensure_process_ownership_finalization_context(
            service,
            proc,
            job_kind,
            resolved=resolved,
            metadata=watcher_metadata,
        )
        lease = None
        try:
            register_active_process = getattr(service, "_register_active_spawned_process", None)
            if callable(register_active_process):
                register_active_process(proc, job_kind)
            pending_lease = getattr(service, "_consume_pending_lifecycle_lease", None)
            lease = pending_lease() if callable(pending_lease) else None
            if lease is not None:
                activate = getattr(lease, "activate", None)
                if not callable(activate):
                    raise RuntimeError("Pending lifecycle lease does not support activation.")
                activate(int(proc.pid))
                cast(Any, proc)._mediapipeline_lifecycle_lease = lease
            active_job_record_path = service._write_active_job_launch_record(
                proc,
                resolved=resolved,
                job_kind=job_kind,
                mode=mode,
                command_line=command_line,
                args=args,
                launch_cwd=launch_cwd,
                show_console=show_console,
                metadata=metadata or {},
            )
            if job_kind == "rerun_csv":
                watcher_metadata["active_jobs_path"] = str(active_job_record_path or "")
                _ensure_process_ownership_finalization_context(
                    service,
                    proc,
                    job_kind,
                    resolved=resolved,
                    metadata=watcher_metadata,
                )
            service._verify_spawn_readiness(proc, command_line)
            _start_active_job_heartbeat_watcher(service, proc, job_kind)
            if not _start_active_job_completion_watcher(
                service,
                proc,
                job_kind,
                resolved=resolved,
                metadata=watcher_metadata,
            ):
                raise RuntimeError(f"Could not start required {job_kind} process completion ownership watcher.")
        except Exception as launch_exc:
            _mark_process_ownership_launch_failed(proc)
            try:
                cleanup_failure = _stop_started_process_after_launch_failure(service, proc, job_kind)
            except Exception as cleanup_exc:
                cleanup_failure = (
                    f"Could not verify that the {job_kind} process exited after launch failure because cleanup raised "
                    f"{type(cleanup_exc).__name__}: {cleanup_exc}"
                )
                service.logger.warning("%s", cleanup_failure)
            if not cleanup_failure:
                finalized = _finalize_process_ownership_after_tree_proof(
                    proc,
                    getattr(proc, "returncode", None),
                )
                if not finalized:
                    cleanup_failure = (
                        f"The {job_kind} process tree exited after launch failure, but exact ownership finalization "
                        "did not complete."
                    )
                    service.logger.warning("%s", cleanup_failure)
            if cleanup_failure:
                lease_note = "No lifecycle lease was available to preserve."
                if lease is not None:
                    try:
                        _mark_launch_cleanup_reconciliation_required(lease)
                        lease_note = "The lifecycle lease was preserved for reconciliation."
                    except Exception as marker_exc:
                        lease_note = (
                            "The lifecycle lease could not be marked for reconciliation: "
                            f"{type(marker_exc).__name__}: {marker_exc}"
                        )
                        service.logger.warning("%s", lease_note)
                note = f"{cleanup_failure} {lease_note}"
                add_note = getattr(launch_exc, "add_note", None)
                if callable(add_note):
                    add_note(note)
            # Structured handoff to the launch facade: Popen succeeded, but
            # ownership setup failed. The facade may terminalize a pre-spawn
            # Run Monitor only when this cleanup was conclusively verified.
            try:
                launch_exc.__dict__["_mediapipeline_process_started"] = True
                launch_exc.__dict__["_mediapipeline_cleanup_verified"] = not bool(cleanup_failure)
            except Exception:
                pass
            raise
        return proc
    finally:
        stdout_handle.close()
        stderr_handle.close()
