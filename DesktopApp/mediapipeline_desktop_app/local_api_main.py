from __future__ import annotations

import argparse
import json
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Any
from typing import Sequence

from .api import LocalApiServer
from .api.http_helpers import NO_TOKEN_DEV_ENV_VAR, no_token_dev_allowed
from .application import MediaPipelineApplicationFacade
from .backend_bootstrap import BOOTSTRAP_SCHEMA_VERSION, backend_bootstrap_payload, startup_progress_payload, startup_step
from .models import ResolvedPaths
from .services import DesktopAppService


StartupProgressCallback = Callable[[dict[str, Any]], None]


class BackendResolvedState:
    def __init__(self, service: DesktopAppService, pipeline_path: Path, config_path: Path) -> None:
        self.service = service
        self.pipeline_path = pipeline_path
        self.config_path = config_path
        self._lock = threading.Lock()
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
        return resolved


def parse_args(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Start the MediaPipeline local backend API.")
    parser.add_argument("--app-root", default="", help="DesktopApp root. Defaults to the bundled DesktopApp folder.")
    parser.add_argument("--pipeline-path", default="", help="Pipeline script path. Defaults to the bundled pipeline script.")
    parser.add_argument("--config-path", default="", help="Config PSD1 path. Defaults to the bundled live config path.")
    parser.add_argument("--host", default="127.0.0.1", help="Bind host. Keep 127.0.0.1 for local desktop shells.")
    parser.add_argument("--port", type=int, default=0, help="Bind port. Use 0 to let Windows choose a free port.")
    parser.add_argument("--token", default="", help="Optional explicit bearer token for the local shell.")
    parser.add_argument("--shell-surface", default="webview", choices=("webview", "tauri"), help="Frontend shell surface label exposed to WebView evidence payloads.")
    parser.add_argument("--emit-startup-progress", action="store_true", help="Emit startup checkpoint JSON lines before the final bootstrap payload.")
    parser.add_argument("--no-token", action="store_true", help="Disable token checks. Intended only for isolated development.")
    return parser.parse_args(argv)


def default_app_root() -> Path:
    return Path(__file__).resolve().parents[1]


def record_startup_step(
    steps: list[dict[str, Any]],
    step_id: str,
    label: str,
    *,
    detail: str = "",
    status: str = "complete",
    callback: StartupProgressCallback | None = None,
) -> dict[str, Any]:
    steps.append(startup_step(step_id, label, status=status, detail=detail))
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
    startup_progress = record_startup_step(
        startup_steps,
        "resolve_app_root",
        "Resolve app root",
        detail=str(root),
        callback=startup_progress_callback,
    )
    service = DesktopAppService(root)
    startup_progress = record_startup_step(
        startup_steps,
        "create_service",
        "Create backend service",
        detail=type(service).__name__,
        callback=startup_progress_callback,
    )
    selected_pipeline_path = pipeline_path or service.default_pipeline_path()
    startup_progress = record_startup_step(
        startup_steps,
        "resolve_pipeline_path",
        "Resolve pipeline path",
        detail=str(selected_pipeline_path),
        callback=startup_progress_callback,
    )
    selected_config_path = config_path or service.default_config_path()
    startup_progress = record_startup_step(
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
    resolved = resolved_state.get()
    startup_progress = record_startup_step(
        startup_steps,
        "resolve_paths",
        "Resolve runtime paths",
        detail=f"workspace={resolved.workspace_root}",
        callback=startup_progress_callback,
    )
    startup_progress = record_startup_step(
        startup_steps,
        "verify_powershell",
        "Verify PowerShell host",
        detail=str(resolved.powershell_host or "not resolved"),
        status="complete" if resolved.powershell_host else "warning",
        callback=startup_progress_callback,
    )
    pipeline_root = selected_pipeline_path.parent
    startup_progress = record_startup_path_step(
        startup_steps,
        "verify_ffmpeg",
        "Verify FFmpeg",
        pipeline_root / "Tools" / "ffmpeg" / "bin" / "ffmpeg.exe",
        callback=startup_progress_callback,
    )
    startup_progress = record_startup_path_step(
        startup_steps,
        "verify_ffprobe",
        "Verify ffprobe",
        pipeline_root / "Tools" / "ffmpeg" / "bin" / "ffprobe.exe",
        callback=startup_progress_callback,
    )
    startup_progress = record_startup_path_step(
        startup_steps,
        "verify_mkvmerge",
        "Verify MKVToolNix",
        pipeline_root / "Tools" / "MKVToolNix" / "mkvmerge.exe",
        callback=startup_progress_callback,
    )
    startup_progress = record_startup_step(
        startup_steps,
        "resolve_state_paths",
        "Resolve state paths",
        detail=f"state={resolved.state_root or ''}; progress={resolved.progress_file or ''}",
        callback=startup_progress_callback,
    )
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
        command_journal_path=root / "RunLogs" / "local_api_command_history.json",
        shell_surface=shell_surface,
        startup_progress=startup_progress,
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
    try:
        service.start_background_tasks()
        startup_steps = list(server.startup_progress.get("steps", [])) if isinstance(server.startup_progress, dict) else []
        server.set_startup_progress(
            record_startup_step(
                startup_steps,
                "start_background_tasks",
                "Start background tasks",
                detail="telemetry sampler ready",
                callback=startup_callback,
            )
        )
        server.start()
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
        while not stop_event.wait(3600.0):
            pass
    except KeyboardInterrupt:
        return 0
    finally:
        server.stop()
        service.stop_background_tasks()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
