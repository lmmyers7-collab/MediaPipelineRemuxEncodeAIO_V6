from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import http.server
import logging
import secrets
import sys
import threading
import time
from pathlib import Path
from typing import Any

from ..application import MediaPipelineApplicationFacade
from ..models import ResolvedPaths, Snapshot
from .command_journal import CommandJournal
from mediapipeline.core.processes.lifecycle_lease import LifecycleLeaseStore
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
SNAPSHOT_CACHE_TTL_SECONDS = 1.0
SNAPSHOT_INITIALIZING_MESSAGE = "Dashboard status is loading in the background."
SNAPSHOT_REFRESH_PENDING_MESSAGE = "Dashboard status is refreshing in the background. Showing the last known status."
SNAPSHOT_REFRESH_FAILED_MESSAGE = "Dashboard status could not be refreshed. Retrying in the background."


def _windows_path_picker_adapter(**kwargs: Any) -> dict[str, Any]:
    picker_kwargs = dict(kwargs)
    picker_kwargs.pop("target_key", None)
    picker_kwargs.pop("setting_key", None)
    return select_windows_paths_with_dialog(**picker_kwargs)


def _journal_state_root(resolved: ResolvedPaths | None) -> Path | None:
    if resolved is None:
        return None
    if resolved.state_root is not None:
        return resolved.state_root
    active_jobs = getattr(resolved, "active_jobs_path", None)
    return Path(active_jobs).parent if active_jobs else None


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
        journal_state_root = _journal_state_root(resolved)
        if command_journal_path is None and journal_state_root is not None:
            command_journal_path = journal_state_root / "RunLogs" / "local_api_command_history.json"
        self.command_journal = CommandJournal(
            path=command_journal_path,
            state_db_root=journal_state_root,
            logger=self.logger,
        )
        self._server: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None
        self._snapshot_cache_lock = threading.Lock()
        self._snapshot_cache: Snapshot | None = None
        self._snapshot_cache_at_monotonic = 0.0
        self._snapshot_refresh_lock = threading.Lock()
        self._snapshot_refresh_thread: threading.Thread | None = None
        self._snapshot_refresh_error = ""

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
        self._schedule_snapshot_refresh()

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
        refresh_thread = self._snapshot_refresh_thread
        if refresh_thread and refresh_thread.is_alive():
            refresh_thread.join(timeout=0.25)

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
            self.command_journal.state_db_root = _journal_state_root(resolved)
        except Exception as exc:
            self.logger.warning("Could not refresh SQLite command journal state root: %s", exc)
        self.command_journal.record(payload, request=request, strict=strict)

    def _mark_command_evidence_indeterminate(self, *, command_id: str, route: str, reason: str) -> None:
        """Durably block close/retry when post-mutation journal evidence fails."""
        resolved = self._resolved()
        if resolved is None or resolved.state_root is None:
            self.logger.error("Critical command evidence is indeterminate but no lifecycle state root is available.")
            return
        try:
            LifecycleLeaseStore(resolved.state_root).mark_indeterminate(
                command_id=command_id,
                route=route,
                reason=reason,
            )
        except Exception as exc:
            self.logger.exception("Could not persist critical command indeterminate marker: %s", exc)

    def _validate_api_payload(self, route: str, body: dict[str, Any]) -> dict[str, Any]:
        from mediapipeline.core.validation.boundary import validate_api_payload

        return validate_api_payload(route, body)

    def _snapshot(self) -> Snapshot | None:
        with self._snapshot_cache_lock:
            snapshot = self._snapshot_cache
            cached_at = self._snapshot_cache_at_monotonic
        if snapshot is not None and time.monotonic() - cached_at < SNAPSHOT_CACHE_TTL_SECONDS:
            return snapshot

        self._schedule_snapshot_refresh()
        if snapshot is None:
            return self._initializing_snapshot()
        return replace(snapshot, last_error=f"SNAPSHOT_REFRESH_PENDING: {SNAPSHOT_REFRESH_PENDING_MESSAGE}")

    def _schedule_snapshot_refresh(self) -> None:
        if not self._snapshot_refresh_lock.acquire(blocking=False):
            return
        thread = threading.Thread(target=self._refresh_snapshot_cache, name="MediaPipelineSnapshotRefresh", daemon=True)
        self._snapshot_refresh_thread = thread
        thread.start()

    def _refresh_snapshot_cache(self) -> None:
        started = time.monotonic()
        try:
            if self.snapshot_provider is not None:
                snapshot = self.snapshot_provider()
            else:
                resolved = self._resolved()
                if resolved is None:
                    return
                build_snapshot = getattr(self.facade.service, "build_snapshot", None)
                if not callable(build_snapshot):
                    return
                audit_root = self.audit_root_provider() if self.audit_root_provider is not None else ""
                snapshot = build_snapshot(resolved, audit_root)
            if not isinstance(snapshot, Snapshot):
                raise RuntimeError("Snapshot refresh returned an invalid response.")
            with self._snapshot_cache_lock:
                self._snapshot_cache = snapshot
                self._snapshot_cache_at_monotonic = time.monotonic()
                self._snapshot_refresh_error = ""
            self.logger.info("Snapshot refresh completed in %.0f ms.", (time.monotonic() - started) * 1000)
        except Exception as exc:
            self._snapshot_refresh_error = str(exc)
            self.logger.exception(
                "Snapshot refresh failed after %.0f ms; code=SNAPSHOT_READ_FAILED detail=%s",
                (time.monotonic() - started) * 1000,
                exc,
            )
        finally:
            self._snapshot_refresh_lock.release()

    def _initializing_snapshot(self) -> Snapshot | None:
        resolved = self._resolved()
        if resolved is None:
            return None
        code = "SNAPSHOT_READ_FAILED" if self._snapshot_refresh_error else "SNAPSHOT_INITIALIZING"
        message = SNAPSHOT_REFRESH_FAILED_MESSAGE if self._snapshot_refresh_error else SNAPSHOT_INITIALIZING_MESSAGE
        return Snapshot(
            resolved=resolved,
            current_activity="Backend status is loading.",
            status_summary="Backend status is loading.",
            log_tail="",
            progress={"Status": "initializing"},
            audit_progress=None,
            latest_failure_report=None,
            latest_failure_json=None,
            latest_audit_csv=None,
            latest_priority_csv=None,
            last_error=f"{code}: {message}",
        )

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
