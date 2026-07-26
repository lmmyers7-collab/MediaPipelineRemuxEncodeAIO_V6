from __future__ import annotations

import argparse
import json
import threading
import time
from collections.abc import Callable
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from typing import Any
from collections.abc import Sequence

from mediapipeline.core.config.identity import config_identity_block_reasons
from mediapipeline.core.config.recovery import ensure_canonical_config, restore_verified_last_good_config
from mediapipeline.core.processes.recovery import LifecycleRecoveryCoordinator
from mediapipeline.core.processes.rerun_lifecycle import reconcile_local_rerun_enrollments
from mediapipeline.core.api.file_overrides.remux_pilot import file_override_remux_pilot_auto_promote_payload

from .api import LocalApiServer
from .api.http_helpers import NO_TOKEN_DEV_ENV_VAR, no_token_dev_allowed
from .application import MediaPipelineApplicationFacade
from .backend_instance import (
    BACKEND_INSTANCE_ERROR_SCHEMA_VERSION,
    BackendInstanceAlreadyRunning,
    BackendInstanceGuard,
    default_backend_instance_state_root,
)
from .backend_bootstrap import BOOTSTRAP_SCHEMA_VERSION, backend_bootstrap_payload, startup_progress_payload, startup_step
from .models import ResolvedPaths
from .services import DesktopAppService


StartupProgressCallback = Callable[[dict[str, Any]], None]
_STARTUP_TIMERS: dict[int, tuple[list[dict[str, Any]], float, float]] = {}


class BackendResolvedState:
    def __init__(self, service: DesktopAppService, pipeline_path: Path, config_path: Path) -> None:
        self.service = service
        self.pipeline_path = pipeline_path
        self.config_path = config_path
        self._lock = threading.Lock()
        self._reload_callbacks: list[Callable[[ResolvedPaths], None]] = []
        self._resolved = self._resolve()

    def _resolve(self) -> ResolvedPaths:
        return self.service.resolve_paths(str(self.pipeline_path), str(self.config_path))

    def get(self) -> ResolvedPaths:
        with self._lock:
            return self._resolved

    def reload(self) -> ResolvedPaths:
        resolved = self._resolve()
        with self._lock:
            self._resolved = resolved
            callbacks = list(self._reload_callbacks)
        for callback in callbacks:
            callback(resolved)
        return resolved

    def add_reload_callback(self, callback: Callable[[ResolvedPaths], None]) -> None:
        with self._lock:
            self._reload_callbacks.append(callback)


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the MediaPipeline local backend API.")
    parser.add_argument("--app-root", default="", help="Desktop app root. Defaults to apps/desktop.")
    parser.add_argument("--pipeline-path", default="", help="Pipeline script path. Defaults to the bundled pipeline script.")
    parser.add_argument("--config-path", default="", help="Config PSD1 path. Defaults to the bundled live config path.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Keep 127.0.0.1 for local desktop shells.")
    parser.add_argument("--port", type=int, default=0, help="Bind port. Use 0 to let Windows choose a free port.")
    parser.add_argument("--token", default="", help="Optional explicit bearer token for the local shell.")
    parser.add_argument("--shell-surface", default="webview", choices=("webview", "tauri"), help="Frontend shell surface label exposed to WebView evidence payloads.")
    parser.add_argument(
        "--instance-state-root",
        default="",
        help="Backend ownership metadata root. Defaults to the per-user LocalAppData lifecycle root.",
    )
    parser.add_argument("--emit-startup-progress", action="store_true", help="Emit startup checkpoint JSON lines before the final bootstrap payload.")
    parser.add_argument("--no-token", action="store_true", help="Disable token checks. Intended only for isolated development.")
    return parser.parse_args(argv)


def default_app_root() -> Path:
    return find_repo_root(Path(__file__)) / "apps" / "desktop"


def _record_pipeline_terminal_command_evidence(
    server: LocalApiServer,
    *,
    command_id: str,
    phase: str,
    return_code: int | None,
    pid: int,
    mode: str,
) -> None:
    ok = phase == "completed"
    payload = {
        "schema_version": "desktop_command_result.v1",
        "command": "pipeline.start",
        "ok": ok,
        "severity": "info" if ok else ("warning" if phase == "interrupted" else "error"),
        "message": (
            f"Pipeline PID {pid} completed."
            if ok
            else f"Pipeline PID {pid} ended with {phase} evidence (return code {return_code})."
        ),
        "refresh_hint": "snapshot",
        "data": {
            "command_id": command_id,
            "route": "/api/pipeline/start",
            "evidence_phase": phase,
            "journal_durability": "strict",
            "pid": pid,
            "mode": mode,
            "return_code": return_code,
        },
    }
    try:
        server._record_command_journal(
            payload,
            request={"_command_id": command_id, "mode": mode},
            strict=True,
        )
    except Exception as exc:
        server._mark_command_evidence_indeterminate(
            command_id=command_id,
            route="/api/pipeline/start",
            reason=f"Terminal pipeline command evidence could not be persisted: {exc}",
        )
        raise


def record_startup_step(
    steps: list[dict[str, Any]],
    step_id: str,
    label: str,
    *,
    detail: str = "",
    status: str = "complete",
    callback: StartupProgressCallback | None = None,
) -> dict[str, Any]:
    now = time.monotonic()
    timer_key = id(steps)
    tracked_steps, started_at, previous_at = _STARTUP_TIMERS.get(timer_key, (steps, now, now))
    if tracked_steps is not steps:
        started_at = now
        previous_at = now
    _STARTUP_TIMERS[timer_key] = (steps, started_at, now)
    steps.append(
        startup_step(
            step_id,
            label,
            status=status,
            detail=detail,
            duration_ms=(now - previous_at) * 1000,
            elapsed_ms=(now - started_at) * 1000,
        )
    )
    progress = startup_progress_payload(steps)
    if callback is not None:
        callback(progress)
    return progress


def record_startup_path_step(
    steps: list[dict[str, Any]],
    step_id: str,
    label: str,
    path: Path | str | None,
    *,
    callback: StartupProgressCallback | None = None,
) -> dict[str, Any]:
    path_text = str(path or "")
    exists = bool(path_text) and Path(path_text).exists()
    detail = path_text if exists else f"missing: {path_text or 'not resolved'}"
    return record_startup_step(
        steps,
        step_id,
        label,
        detail=detail,
        status="complete" if exists else "warning",
        callback=callback,
    )


def build_backend(
    *,
    app_root: Path | None = None,
    pipeline_path: Path | None = None,
    config_path: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 0,
    token: str | None = None,
    require_token: bool = True,
    shell_surface: str = "webview",
    shutdown_request: threading.Event | None = None,
    startup_progress_callback: StartupProgressCallback | None = None,
) -> tuple[DesktopAppService, ResolvedPaths, LocalApiServer]:
    startup_steps: list[dict[str, Any]] = []
    root = (app_root or default_app_root()).resolve()
    record_startup_step(
        startup_steps,
        "resolve_app_root",
        "Resolve app root",
        detail=str(root),
        callback=startup_progress_callback,
    )
    service = DesktopAppService(root)
    record_startup_step(
        startup_steps,
        "create_service",
        "Create backend service",
        detail=type(service).__name__,
        callback=startup_progress_callback,
    )
    selected_pipeline_path = pipeline_path or service.default_pipeline_path()
    record_startup_step(
        startup_steps,
        "resolve_pipeline_path",
        "Resolve pipeline path",
        detail=str(selected_pipeline_path),
        callback=startup_progress_callback,
    )
    if config_path is not None:
        selected_config_path = config_path
    else:
        recovery = ensure_canonical_config(service.app_root, service.workspace_root)
        record_startup_step(
            startup_steps,
            "recover_config",
            "Recover live config",
            detail=recovery.message,
            status="complete" if recovery.ok else "warning",
            callback=startup_progress_callback,
        )
        # recovery resolves the canonical local config, completes the legacy
        # rename, or points at the per-user config (packaged builds). Use it as
        # the selection so dev and packaged shells agree.
        selected_config_path = recovery.canonical_path
    record_startup_step(
        startup_steps,
        "resolve_config_path",
        "Resolve config path",
        detail=str(selected_config_path),
        callback=startup_progress_callback,
    )
    resolved_state = BackendResolvedState(
        service,
        selected_pipeline_path,
        selected_config_path,
    )
    service.configure_remux_pilot_auto_promotion(
        resolved_provider=resolved_state.get,
        payload_builder=file_override_remux_pilot_auto_promote_payload,
    )
    service.configure_active_job_reconciliation(resolved_state.get)
    resolved = resolved_state.get()
    record_startup_step(
        startup_steps,
        "resolve_paths",
        "Resolve runtime paths",
        detail=f"workspace={resolved.workspace_root}",
        callback=startup_progress_callback,
    )
    if config_path is None:
        config_block_reasons = config_identity_block_reasons(getattr(resolved, "config_identity", {}) or {})
        if config_block_reasons:
            recovery = restore_verified_last_good_config(
                selected_config_path,
                app_root=service.app_root,
                workspace_root=service.workspace_root,
                powershell_host=resolved.powershell_host,
                load_config_data=service.load_config_data,
                local_base=resolved.local_base,
            )
            record_startup_step(
                startup_steps,
                "repair_blocked_config",
                "Repair blocked config",
                detail=recovery.message,
                status="complete" if recovery.ok else "warning",
                callback=startup_progress_callback,
            )
            if recovery.ok:
                resolved = resolved_state.reload()
    config_loaded = bool(getattr(resolved, "config_data", None))
    record_startup_step(
        startup_steps,
        "verify_config_loaded",
        "Verify settings loaded",
        detail="settings loaded" if config_loaded else f"settings NOT loaded from {resolved.config_path}",
        status="complete" if config_loaded else "warning",
        callback=startup_progress_callback,
    )
    record_startup_step(
        startup_steps,
        "verify_powershell",
        "Verify PowerShell host",
        detail=str(resolved.powershell_host or "not resolved"),
        status="complete" if resolved.powershell_host else "warning",
        callback=startup_progress_callback,
    )
    pipeline_root = selected_pipeline_path.parent
    if pipeline_root.name.casefold() == "entrypoints":
        pipeline_root = pipeline_root.parent
    record_startup_path_step(
        startup_steps,
        "verify_ffmpeg",
        "Verify FFmpeg",
        pipeline_root / "tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
        callback=startup_progress_callback,
    )
    record_startup_path_step(
        startup_steps,
        "verify_ffprobe",
        "Verify ffprobe",
        pipeline_root / "tools" / "ffmpeg" / "bin" / "ffprobe.exe",
        callback=startup_progress_callback,
    )
    record_startup_path_step(
        startup_steps,
        "verify_mkvmerge",
        "Verify MKVToolNix",
        pipeline_root / "tools" / "MKVToolNix" / "mkvmerge.exe",
        callback=startup_progress_callback,
    )
    record_startup_step(
        startup_steps,
        "resolve_state_paths",
        "Resolve state paths",
        detail=f"state={resolved.state_root or ''}; progress={resolved.progress_file or ''}",
        callback=startup_progress_callback,
    )
    rerun_reconciliation = reconcile_local_rerun_enrollments(resolved)
    record_startup_step(
        startup_steps,
        "reconcile_local_reruns",
        "Reconcile local CSV reruns",
        detail=(
            f"checked={rerun_reconciliation.get('checked_count', 0)}; "
            f"alive={rerun_reconciliation.get('alive_count', 0)}; "
            f"terminalized={rerun_reconciliation.get('terminalized_count', 0)}; "
            f"replayed={rerun_reconciliation.get('replayed_count', 0)}"
        ),
        status="complete" if rerun_reconciliation.get("persisted") is not False else "warning",
        callback=startup_progress_callback,
    )

    def _reconcile_local_reruns_after_reload(reloaded: ResolvedPaths) -> None:
        reconcile_local_rerun_enrollments(reloaded)

    resolved_state.add_reload_callback(_reconcile_local_reruns_after_reload)
    facade = MediaPipelineApplicationFacade(service)
    startup_progress = record_startup_step(
        startup_steps,
        "create_facade",
        "Create application facade",
        detail=type(facade).__name__,
        callback=startup_progress_callback,
    )
    server = LocalApiServer(
        facade,
        host=host,
        port=port,
        token=token or None,
        require_token=require_token,
        resolved_provider=resolved_state.get,
        resolved_reload=resolved_state.reload,
        audit_root_provider=lambda: str(resolved_state.get().audit_reports_path or ""),
        shutdown_request=shutdown_request.set if shutdown_request is not None else None,
        command_journal_path=getattr(service, "command_journal_path", root / "RunLogs" / "local_api_command_history.json"),
        shell_surface=shell_surface,
        startup_progress=startup_progress,
    )

    service.configure_process_terminal_command_evidence(
        lambda **evidence: _record_pipeline_terminal_command_evidence(server, **evidence)
    )
    startup_progress = record_startup_step(
        startup_steps,
        "create_local_api",
        "Create local API server",
        detail=f"{host}:{port}",
        callback=startup_progress_callback,
    )
    server.set_startup_progress(startup_progress)
    return service, resolved, server


def bootstrap_payload(
    server: LocalApiServer,
    resolved: ResolvedPaths,
    *,
    include_token: bool,
    shell_surface: str | None = None,
) -> dict[str, object]:
    return backend_bootstrap_payload(
        url=server.url,
        token=server.token,
        host=server.host,
        port=server.port,
        config_path=resolved.config_path,
        pipeline_path=resolved.pipeline_path,
        include_token=include_token,
        shell_surface=shell_surface or getattr(server, "shell_surface", "webview"),
        startup_progress=getattr(server, "startup_progress", None),
    )


def emit_startup_progress(progress: dict[str, Any]) -> None:
    print(json.dumps(progress, sort_keys=True), flush=True)


def main(argv: Sequence[str] | None = None) -> int:
    args = parse_args(argv)
    app_root = Path(args.app_root).expanduser() if args.app_root else None
    pipeline_path = Path(args.pipeline_path).expanduser() if args.pipeline_path else None
    config_path = Path(args.config_path).expanduser() if args.config_path else None
    host = str(args.host or "127.0.0.1")
    if bool(args.no_token) and not no_token_dev_allowed(host):
        print(
            json.dumps(
                {
                    "error": (
                        f"--no-token requires a loopback --host and {NO_TOKEN_DEV_ENV_VAR}=1. "
                        "Token checks remain enabled by default."
                    )
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 2
    require_token = not bool(args.no_token)
    stop_event = threading.Event()
    startup_callback = emit_startup_progress if bool(args.emit_startup_progress) else None
    instance_state_root = (
        Path(args.instance_state_root).expanduser()
        if str(args.instance_state_root or "").strip()
        else default_backend_instance_state_root()
    )
    try:
        instance_guard = BackendInstanceGuard.acquire(
            instance_state_root,
            shell_surface=str(args.shell_surface or "webview"),
        )
    except BackendInstanceAlreadyRunning as exc:
        print(
            json.dumps(
                {
                    "schema_version": BACKEND_INSTANCE_ERROR_SCHEMA_VERSION,
                    "error": str(exc),
                },
                sort_keys=True,
            ),
            flush=True,
        )
        return 3
    try:
        service, resolved, server = build_backend(
            app_root=app_root,
            pipeline_path=pipeline_path,
            config_path=config_path,
            host=host,
            port=int(args.port or 0),
            token=str(args.token or "") or None,
            require_token=require_token,
            shell_surface=str(args.shell_surface or "webview"),
            shutdown_request=stop_event,
            startup_progress_callback=startup_callback,
        )
    except BaseException:
        try:
            instance_guard.mark_cleanup()
        finally:
            instance_guard.release()
        raise
    try:
        def current_resolved() -> ResolvedPaths:
            provider = server.resolved_provider
            current = provider() if callable(provider) else None
            return current if current is not None else resolved

        service.start_background_tasks()
        startup_steps = list(server.startup_progress.get("steps", [])) if isinstance(server.startup_progress, dict) else []
        server.set_startup_progress(
            record_startup_step(
                startup_steps,
                "start_background_tasks",
                "Start background tasks",
                detail="telemetry sampler and remux pilot monitor ready",
                callback=startup_callback,
            )
        )
        server.start()
        instance_guard.mark_listening(server.url)
        startup_steps = list(server.startup_progress.get("steps", [])) if isinstance(server.startup_progress, dict) else []
        server.set_startup_progress(
            record_startup_step(
                startup_steps,
                "server_listening",
                "Start local API listener",
                detail=server.url,
                callback=startup_callback,
            )
        )
        print(json.dumps(bootstrap_payload(server, resolved, include_token=require_token), sort_keys=True), flush=True)
        # Reconcile durable lifecycle ownership before a watcher can create a
        # competing launch. The listener remains available for authoritative
        # recovery/close evidence while this bounded reconciliation runs.
        recovery = LifecycleRecoveryCoordinator()
        server.facade.set_recovery_status(recovery.status())

        def _resume_lifecycle_operation(route: str, request: dict[str, Any], original_command_id: str) -> dict[str, Any]:
            recovery_command_id = f"{original_command_id}-recovery"
            replay = {**dict(request), "_command_id": recovery_command_id}
            try:
                if route == "/api/pipeline/start":
                    result = server.facade.start_pipeline_process(current_resolved(), replay)
                elif route == "/api/audit/start":
                    result = server.facade.start_audit_process(current_resolved(), replay)
                elif route == "/api/rerun/start":
                    result = server.facade.start_rerun_csv_process(current_resolved(), replay)
                else:
                    return {"ok": False, "message": f"No backend recovery executor is registered for {route}."}
                payload = result.to_mapping()
                data = dict(payload.get("data") or {})
                data.update({"command_id": recovery_command_id, "recovery_of_command_id": original_command_id, "evidence_phase": "recovery_terminal"})
                payload["data"] = data
                server._record_command_journal(payload, request=replay, strict=True)
                return payload
            except Exception as exc:
                return {"ok": False, "message": f"Automatic recovery execution failed: {exc}"}

        recovery_status = recovery.run(current_resolved(), resume=_resume_lifecycle_operation)
        server.facade.set_recovery_status(recovery_status)
        # Started after the listener and bootstrap line so an enabled watcher's
        # first scan of large/remote roots can never delay backend reachability.
        startup_steps = list(server.startup_progress.get("steps", [])) if isinstance(server.startup_progress, dict) else []
        try:
            watch_state = server.facade._start_watch_folder_manager(
                resolved_provider=server.resolved_provider,
                resolved_reload=server.resolved_reload,
            )
            if not bool(watch_state.get("enabled", False)):
                watch_detail = "disabled"
                watch_status = "complete"
            elif str(watch_state.get("status") or "").casefold() == "degraded":
                watch_detail = f"degraded: {watch_state.get('reason') or watch_state.get('last_error') or 'unknown'}"
                watch_status = "warning"
            else:
                watch_detail = f"started ({len(watch_state.get('roots') or [])} roots)"
                watch_status = "complete"
        except Exception as exc:
            watch_detail = f"degraded: {exc}"
            watch_status = "warning"
        server.set_startup_progress(
            record_startup_step(
                startup_steps,
                "watch_folders",
                "Start watch-folder manager",
                detail=watch_detail,
                status=watch_status,
                callback=startup_callback,
            )
        )
        while not stop_event.wait(3600.0):
            pass
    except KeyboardInterrupt:
        return 0
    finally:
        try:
            instance_guard.mark_cleanup()
        except Exception as exc:
            print(
                json.dumps(
                    {
                        "schema_version": BACKEND_INSTANCE_ERROR_SCHEMA_VERSION,
                        "error": f"Backend cleanup ownership metadata could not be updated: {exc}",
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        try:
            server.stop()
        finally:
            try:
                service.stop_background_tasks()
            finally:
                instance_guard.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "BOOTSTRAP_SCHEMA_VERSION",
    "BackendResolvedState",
    "StartupProgressCallback",
    "bootstrap_payload",
    "build_backend",
    "default_app_root",
    "emit_startup_progress",
    "main",
    "parse_args",
    "record_startup_path_step",
    "record_startup_step",
]
