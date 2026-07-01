from __future__ import annotations

from collections.abc import Callable
import http.server
import logging
import secrets
import sys
import threading
from pathlib import Path
from typing import Any

from ..application import MediaPipelineApplicationFacade
from ..models import ResolvedPaths, Snapshot
from .command_journal import CommandJournal
from mediapipeline.core.api.command_handlers import LocalApiCommandHandlerMixin
from .handler import build_local_api_handler_class
from .http_helpers import (
    host_header_authorized,
    is_client_disconnect_error,
    local_api_allowed_origins,
    local_api_auth_cookie_header,
    origin_header_authorized,
    request_authorized,
)
from .path_dialogs import select_windows_paths_with_dialog
from .read_payloads import LocalApiReadPayloadMixin
from .static_files import default_static_root, local_api_bootstrap, read_static_asset, render_index


ResolvedProvider = Callable[[], ResolvedPaths | None]
ResolvedReload = Callable[[], ResolvedPaths | None]
SnapshotProvider = Callable[[], Snapshot | None]
AuditRootProvider = Callable[[], str]
ShutdownRequest = Callable[[], None]


def _windows_path_picker_adapter(**kwargs: Any) -> dict[str, Any]:
    picker_kwargs = dict(kwargs)
    picker_kwargs.pop("target_key", None)
    picker_kwargs.pop("setting_key", None)
    return select_windows_paths_with_dialog(**picker_kwargs)


class _LocalApiThreadingHTTPServer(http.server.ThreadingHTTPServer):
    def __init__(self, *args: Any, logger: logging.Logger, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._logger = logger

    def handle_error(self, request: Any, client_address: Any) -> None:
        exc = sys.exc_info()[1]
        if exc is not None and is_client_disconnect_error(exc):
            self._logger.debug("Local API client disconnected before request completed: %s", client_address)
            return
        super().handle_error(request, client_address)


class LocalApiServer(LocalApiReadPayloadMixin, LocalApiCommandHandlerMixin):
    """Localhost API for WebView/Tauri and browser control surfaces.

    Health and static shell assets are public for startup. Read and command API
    routes require a per-run token by default, unless a dev launcher explicitly
    disables auth.
    """

    def __init__(
        self,
        facade: MediaPipelineApplicationFacade,
        *,
        host: str = "127.0.0.1",
        port: int = 0,
        token: str | None = None,
        require_token: bool = True,
        resolved_provider: ResolvedProvider | None = None,
        resolved_reload: ResolvedReload | None = None,
        snapshot_provider: SnapshotProvider | None = None,
        audit_root_provider: AuditRootProvider | None = None,
        shutdown_request: ShutdownRequest | None = None,
        static_root: Path | None = None,
        command_journal_path: Path | None = None,
        shell_surface: str = "webview",
        startup_progress: dict[str, Any] | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        self.facade = facade
        self.host = host
        self.requested_port = int(port)
        self.token = token or secrets.token_urlsafe(24)
        self.require_token = bool(require_token)
        self.resolved_provider = resolved_provider
        self.resolved_reload = resolved_reload
        self.snapshot_provider = snapshot_provider
        self.audit_root_provider = audit_root_provider
        self.shutdown_request = shutdown_request
        self.static_root = static_root if static_root is not None else default_static_root()
        self.shell_surface = str(shell_surface or "webview")
        self.startup_progress = dict(startup_progress or {})
        self.logger = logger or logging.getLogger(__name__)
        self._path_picker = _windows_path_picker_adapter
        self._rename_path_picker = _windows_path_picker_adapter
        self._settings_path_picker = _windows_path_picker_adapter
        self._pipeline_file_picker = _windows_path_picker_adapter
        resolved = self._resolved()
        self.command_journal = CommandJournal(
            path=command_journal_path,
            state_db_root=resolved.state_root if resolved is not None else None,
            logger=self.logger,
        )
        self._server: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    @property
    def port(self) -> int:
        if self._server is None:
            return self.requested_port
        return int(self._server.server_address[1])

    @property
    def url(self) -> str:
        return f"http://{self.host}:{self.port}"

    def start(self) -> None:
        if self._server is not None:
            return
        handler_cls = build_local_api_handler_class(self)
        server = _LocalApiThreadingHTTPServer((self.host, self.requested_port), handler_cls, logger=self.logger)
        # Command handlers own cleanup/journaling; do not abandon them during backend shutdown.
        server.daemon_threads = False
        self._server = server
        self._thread = threading.Thread(target=server.serve_forever, name="MediaPipelineLocalApi", daemon=True)
        self._thread.start()

    def set_startup_progress(self, startup_progress: dict[str, Any]) -> None:
        self.startup_progress = dict(startup_progress or {})

    def stop(self) -> None:
        cancel_watcher = getattr(self.facade, "_cancel_pipeline_schedule_stop_watcher", None)
        if callable(cancel_watcher):
            cancel_watcher("local API server stopping")
        stop_watch_folders = getattr(self.facade, "_stop_watch_folder_manager", None)
        if callable(stop_watch_folders):
            stop_watch_folders("local API server stopping")
        server = self._server
        if server is None:
            return
        self._server = None
        try:
            server.shutdown()
        finally:
            server.server_close()
        thread = self._thread
        self._thread = None
        if thread and thread.is_alive():
            thread.join(timeout=2.0)

    def _request_authorized(self, headers: Any, query: dict[str, list[str]]) -> bool:
        return request_authorized(headers, query, token=self.token, require_token=self.require_token)

    def _host_header_authorized(self, headers: Any) -> bool:
        return host_header_authorized(str(headers.get("Host") or ""), bind_host=self.host, port=self.port)

    def _origin_header_authorized(self, headers: Any) -> bool:
        return origin_header_authorized(
            str(headers.get("Origin") or ""),
            bind_host=self.host,
            port=self.port,
            shell_surface=self.shell_surface,
        )

    def _cors_response_origin(self, headers: Any) -> str:
        origin = str(headers.get("Origin") or "").strip()
        if origin and self._origin_header_authorized(headers):
            return origin
        allowed_origins = local_api_allowed_origins(bind_host=self.host, port=self.port, shell_surface=self.shell_surface)
        preferred_origin = f"http://127.0.0.1:{self.port}"
        if preferred_origin in allowed_origins:
            return preferred_origin
        return sorted(allowed_origins)[0] if allowed_origins else "http://127.0.0.1"

    def _resolved(self) -> ResolvedPaths | None:
        if self.resolved_provider is None:
            return None
        return self.resolved_provider()

    def _record_command_journal(
        self,
        payload: dict[str, Any],
        *,
        request: dict[str, Any] | None = None,
        strict: bool = False,
    ) -> None:
        try:
            resolved = self._resolved()
            self.command_journal.state_db_root = resolved.state_root if resolved is not None else None
        except Exception as exc:
            self.logger.warning("Could not refresh SQLite command journal state root: %s", exc)
        self.command_journal.record(payload, request=request, strict=strict)

    def _validate_api_payload(self, route: str, body: dict[str, Any]) -> dict[str, Any]:
        from mediapipeline.core.validation.boundary import validate_api_payload

        return validate_api_payload(route, body)

    def _snapshot(self) -> Snapshot | None:
        if self.snapshot_provider is not None:
            snapshot = self.snapshot_provider()
            if snapshot is not None:
                return snapshot
        resolved = self._resolved()
        if resolved is None:
            return None
        build_snapshot = getattr(self.facade.service, "build_snapshot", None)
        if not callable(build_snapshot):
            return None
        audit_root = self.audit_root_provider() if self.audit_root_provider is not None else ""
        snapshot = build_snapshot(resolved, audit_root)
        return snapshot if isinstance(snapshot, Snapshot) else None

    def _send_index(self, handler: http.server.BaseHTTPRequestHandler) -> None:
        response = render_index(
            self.static_root,
            local_api_bootstrap(
                token=self.token,
                require_token=self.require_token,
                app_version=self.facade.app_version,
                shell_surface=self.shell_surface,
                startup_progress=self.startup_progress,
            ),
            logger=self.logger,
        )
        extra_headers: list[tuple[str, str]] = []
        cookie = local_api_auth_cookie_header(
            token=self.token,
            require_token=self.require_token,
            shell_surface=self.shell_surface,
        )
        if response.status == 200 and cookie:
            extra_headers.append(("Set-Cookie", cookie))
        handler._send_bytes(  # type: ignore[attr-defined]
            response.body,
            status=response.status,
            content_type=response.content_type,
            extra_headers=extra_headers,
        )

    def _send_static(self, handler: http.server.BaseHTTPRequestHandler, route: str) -> None:
        response = read_static_asset(self.static_root, route, logger=self.logger)
        handler._send_bytes(response.body, status=response.status, content_type=response.content_type)  # type: ignore[attr-defined]
