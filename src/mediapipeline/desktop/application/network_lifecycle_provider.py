from __future__ import annotations

import logging
import re
import socket
import threading
import time
import uuid
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from mediapipeline.core.kernel.config_keys import (
    KEY_WORKER_AUTH_TOKEN,
    KEY_WORKER_COORDINATOR_URL,
    KEY_WORKER_SOURCE_PATH_MAP,
)
from mediapipeline.core.kernel.models import ResolvedPaths
from mediapipeline.core.network.url_policy import redact_network_secret_text
from mediapipeline.core.processes.pipeline_policy import coordinator_also_encode_locally_enabled
from mediapipeline.desktop.network.coordinator import CoordinatorDispatcher
from mediapipeline.desktop.network.worker import WorkerDispatcher


_log = logging.getLogger(__name__)

# How often the coordinator re-scans the source queue so workers keep getting
# newly added media instead of draining only the start-time snapshot. Honoured
# via the optional CoordinatorQueueRefreshSecs config key; clamped to >= 5s.
COORDINATOR_QUEUE_REFRESH_SECONDS = 15.0
_MIN_QUEUE_REFRESH_SECONDS = 5.0
_RUNNING_WORKER_HOT_APPLY_KEYS = (
    KEY_WORKER_COORDINATOR_URL,
    KEY_WORKER_AUTH_TOKEN,
    KEY_WORKER_SOURCE_PATH_MAP,
)
_RUNNING_WORKER_HOT_APPLY_METHODS = {
    KEY_WORKER_COORDINATOR_URL: "update_coordinator_url",
    KEY_WORKER_AUTH_TOKEN: "update_auth_token",
    KEY_WORKER_SOURCE_PATH_MAP: "update_source_path_map",
}


def _safe_machine_id() -> str:
    try:
        raw = socket.gethostname()
    except Exception:
        raw = ""
    machine_id = re.sub(r"[^A-Za-z0-9._-]+", "-", str(raw or "").strip()).strip(".-_")
    return (machine_id or f"worker-{uuid.uuid4().hex[:12]}")[:64]


class _ImmediateCallbackRoot:
    def after(self, _delay_ms: int, callback: Any, *args: Any) -> None:
        if callable(callback):
            callback(*args)


class _NetworkRuntimeApp:
    def __init__(self, facade: object, resolved: ResolvedPaths, *, role: str) -> None:
        self.facade = facade
        self.service = getattr(facade, "service")
        self.resolved = resolved
        self.role = role
        self.root = _ImmediateCallbackRoot()
        self.queue_records: list[Any] = []
        self.failure_records: list[Any] = []
        self._machine_id = _safe_machine_id()
        self.dispatcher: Any = None
        # Serialises queue_records reference swaps (coordinator queue refresher)
        # against in-place removals and the claim scan in CoordinatorQueueMixin.
        self._queue_lock = threading.Lock()
        self._active_lock = threading.Lock()
        self._active_job: Any = None
        self._active_proc: Any = None

    @property
    def snapshot(self) -> Any:
        build_snapshot = getattr(self.service, "build_snapshot", None)
        if callable(build_snapshot):
            try:
                return build_snapshot(self.resolved, "")
            except Exception as exc:
                _log.warning("Network worker snapshot read failed: %s", exc)
        read_progress = getattr(self.service, "read_progress", None)
        if callable(read_progress):
            try:
                return SimpleNamespace(progress=read_progress(self.resolved) or {})
            except Exception as exc:
                _log.warning("Network worker progress read failed: %s", exc)
        return SimpleNamespace(progress={})

    def post_ui(self, _name: str, callback: Any) -> None:
        self.root.after(0, callback)

    def apply_queue_filters(self) -> None:
        return None

    def _remove_from_queue(self, source_path: str) -> None:
        target = str(source_path or "")
        if not target:
            return
        with self._queue_lock:
            self.queue_records = [
                record
                for record in self.queue_records
                if str(getattr(record, "source_path", "") or "") != target
            ]

    def _worker_start_single_file(self, job: Any) -> None:
        if self.dispatcher is None:
            raise RuntimeError("network dispatcher is not attached")
        self._start_claimed_encode(job, self.dispatcher)

    def _start_claimed_encode(self, job: Any, dispatcher: Any) -> None:
        starter = getattr(self.facade, "_start_network_claimed_job", None)
        if not callable(starter):
            raise RuntimeError("network claimed-job starter is unavailable")
        with self._active_lock:
            if self._active_job is not None:
                raise RuntimeError("another network worker job is already active")
        proc = starter(self, dispatcher, job)
        self._watch_claimed_process(dispatcher, job, proc)

    def _watch_claimed_process(self, dispatcher: Any, job: Any, proc: Any) -> None:
        with self._active_lock:
            self._active_job = job
            self._active_proc = proc
        started_at = time.monotonic()

        def _watch() -> None:
            return_code: int | None = None
            error_text = ""
            try:
                wait = getattr(proc, "wait", None)
                if not callable(wait):
                    raise RuntimeError("launched network worker process has no wait() method")
                return_code = wait()
            except Exception as exc:
                error_text = str(exc)
                _log.warning("Network worker process wait failed for job %s: %s", getattr(job, "job_id", ""), exc)
            finally:
                elapsed = max(0.0, time.monotonic() - started_at)
                success = return_code == 0 and not error_text
                if not success and not error_text:
                    error_text = f"pipeline process exited with code {return_code}"
                try:
                    dispatcher.mark_done(
                        job,
                        success=success,
                        error="" if success else error_text,
                        elapsed_seconds=elapsed,
                        completion_status="processed" if success else "failed",
                        route="network_lifecycle_single_file",
                        queue_terminal=False,
                    )
                except Exception as exc:
                    _log.warning("Network worker done report failed for job %s: %s", getattr(job, "job_id", ""), exc)
                with self._active_lock:
                    if self._active_job is job:
                        self._active_job = None
                        self._active_proc = None

        thread = threading.Thread(
            target=_watch,
            name="network-worker-process-watch",
            daemon=True,
        )
        thread.start()

    def _worker_abort_current_job(self) -> None:
        self.abort_current_worker_job("network worker abort")

    def abort_current_worker_job(self, reason: str) -> None:
        with self._active_lock:
            proc = self._active_proc
        if proc is None:
            return
        kill_tree = getattr(self.service, "kill_process_tree", None)
        if callable(kill_tree):
            kill_tree(proc, reason)
            return
        terminate = getattr(proc, "terminate", None)
        if callable(terminate):
            terminate()

    def active_process_running(self) -> bool:
        with self._active_lock:
            proc = self._active_proc
            job = self._active_job
        if proc is None:
            return False
        poll = getattr(proc, "poll", None)
        if callable(poll):
            try:
                return poll() is None
            except Exception as exc:
                _log.warning("Network worker process poll failed for job %s: %s", getattr(job, "job_id", ""), exc)
                return True
        return job is not None

    def wait_for_active_process_exit(self, timeout_seconds: float = 10.0) -> bool:
        deadline = time.monotonic() + max(0.0, float(timeout_seconds))
        while self.has_active_worker_job() and time.monotonic() < deadline:
            time.sleep(0.1)
        return not self.has_active_worker_job()

    def has_active_worker_job(self) -> bool:
        with self._active_lock:
            return self._active_job is not None


class NetworkLifecycleProviderMixin:
    """Desktop-owned provider methods used by core network lifecycle commands."""

    service: object

    def _network_runtime_entries(self) -> dict[str, dict[str, Any]]:
        runtime = getattr(self, "_network_dispatcher_runtime", None)
        if not isinstance(runtime, dict):
            runtime = {}
            setattr(self, "_network_dispatcher_runtime", runtime)
        return runtime

    def _hot_apply_running_worker_settings(
        self,
        *,
        changed_keys: list[str] | tuple[str, ...] | set[str],
        merged_config: dict[str, Any],
        warnings: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """Apply saved worker settings to a running dispatcher without restart."""
        changed = {str(key) for key in changed_keys}
        relevant = [key for key in _RUNNING_WORKER_HOT_APPLY_KEYS if key in changed]
        if not relevant:
            return []

        runtime = self._network_runtime_entries()
        entry = runtime.get("worker")
        if not isinstance(entry, dict):
            return [{
                "schema_version": "desktop_network_worker_hot_apply.v1",
                "role": "worker",
                "status": "not_running",
                "changed_keys": relevant,
                "message": "Saved worker settings will be used the next time worker polling starts.",
            }]

        dispatcher = entry.get("dispatcher")
        if dispatcher is None:
            return [{
                "schema_version": "desktop_network_worker_hot_apply.v1",
                "role": "worker",
                "status": "not_running",
                "changed_keys": relevant,
                "message": "No running worker dispatcher was available for hot-apply.",
            }]

        updates: list[dict[str, Any]] = []
        for key in relevant:
            method_name = _RUNNING_WORKER_HOT_APPLY_METHODS[key]
            updater = getattr(dispatcher, method_name, None)
            if not callable(updater):
                message = f"Running worker dispatcher does not support {method_name}."
                updates.append({
                    "schema_version": "desktop_network_worker_hot_apply.v1",
                    "role": "worker",
                    "key": key,
                    "status": "skipped",
                    "message": message,
                })
                if warnings is not None:
                    warnings.append(message)
                continue
            try:
                updater(str(merged_config.get(key, "") or ""))
            except Exception as exc:
                safe_exc = redact_network_secret_text(exc)
                message = f"Running worker hot-apply failed for {key}: {safe_exc}"
                self._network_logger().warning("%s", message)
                updates.append({
                    "schema_version": "desktop_network_worker_hot_apply.v1",
                    "role": "worker",
                    "key": key,
                    "status": "failed",
                    "message": message,
                })
                if warnings is not None:
                    warnings.append(message)
            else:
                updates.append({
                    "schema_version": "desktop_network_worker_hot_apply.v1",
                    "role": "worker",
                    "key": key,
                    "status": "applied",
                    "method": method_name,
                })

        app = entry.get("app")
        running_resolved = getattr(app, "resolved", None)
        if running_resolved is not None and hasattr(running_resolved, "config_data"):
            running_resolved.config_data = dict(merged_config)

        applied_keys = [item["key"] for item in updates if item.get("status") == "applied"]
        if applied_keys:
            self._network_logger().info(
                "Network worker settings hot-applied without restart: %s",
                ", ".join(applied_keys),
            )
        return updates

    def _network_logger(self) -> logging.Logger:
        logger = getattr(self.service, "logger", None)
        return logger if isinstance(logger, logging.Logger) else _log

    def _load_network_queue_records(
        self, resolved: ResolvedPaths, *, force_refresh: bool = False
    ) -> list[Any]:
        builder = getattr(self.service, "build_queue_preview", None)
        if not callable(builder):
            return []
        try:
            return list(builder(resolved, force_refresh=force_refresh))
        except TypeError:
            return list(builder(resolved))

    def _load_network_failure_records(self, resolved: ResolvedPaths) -> list[Any]:
        records: list[Any] = []
        marker_loader = getattr(self.service, "load_failure_marker_records", None)
        if callable(marker_loader):
            try:
                records.extend(list(marker_loader(resolved)))
            except Exception as exc:
                self._network_logger().warning("Network failure marker load failed: %s", exc)
        latest = getattr(self.service, "latest_failure_json", None)
        loader = getattr(self.service, "load_failure_records", None)
        if callable(latest) and callable(loader):
            try:
                path = latest(resolved)
                if path:
                    records.extend(list(loader(Path(path))))
            except Exception as exc:
                self._network_logger().warning("Network failure report load failed: %s", exc)
        return records

    def start_network_coordinator(
        self,
        *,
        resolved: ResolvedPaths,
        request: dict[str, Any],
        command_id: str,
    ) -> None:
        _ = request, command_id
        runtime = self._network_runtime_entries()
        if "coordinator" in runtime:
            raise RuntimeError("coordinator dispatcher is already running")
        app = _NetworkRuntimeApp(self, resolved, role="coordinator")
        app.queue_records = self._load_network_queue_records(resolved)
        app.failure_records = self._load_network_failure_records(resolved)
        dispatcher = CoordinatorDispatcher(app)
        app.dispatcher = dispatcher
        entry: dict[str, Any] = {"app": app, "dispatcher": dispatcher}
        # Keep the served queue live so newly added media is distributed
        # instead of only the start-time snapshot draining to idle.
        self._start_coordinator_queue_refresh_loop(entry, resolved)
        if coordinator_also_encode_locally_enabled(resolved.config_data or {}):
            self._start_coordinator_local_worker_loop(entry)
        runtime["coordinator"] = entry

    def stop_network_coordinator(
        self,
        *,
        resolved: ResolvedPaths,
        request: dict[str, Any],
        command_id: str,
    ) -> None:
        _ = resolved, request, command_id
        runtime = self._network_runtime_entries()
        entry = runtime.get("coordinator")
        if not entry:
            return
        queue_refresh_stop = entry.get("queue_refresh_stop")
        if isinstance(queue_refresh_stop, threading.Event):
            queue_refresh_stop.set()
        stop_event = entry.get("local_worker_stop")
        if isinstance(stop_event, threading.Event):
            stop_event.set()
        app = entry.get("app")
        if isinstance(app, _NetworkRuntimeApp):
            app.abort_current_worker_job("network coordinator stop")
            if app.has_active_worker_job() and not app.wait_for_active_process_exit(timeout_seconds=10.0):
                self._network_logger().warning(
                    "Coordinator stop requested but the local worker process is still running; leaving its claim for recovery/reclaim."
                )
        dispatcher = entry.get("dispatcher")
        try:
            shutdown = getattr(dispatcher, "shutdown", None)
            if callable(shutdown):
                shutdown()
        finally:
            for thread_key in ("local_worker_thread", "queue_refresh_thread"):
                thread = entry.get(thread_key)
                if isinstance(thread, threading.Thread) and thread is not threading.current_thread():
                    thread.join(timeout=5.0)
            runtime.pop("coordinator", None)

    def start_network_worker(
        self,
        *,
        resolved: ResolvedPaths,
        request: dict[str, Any],
        command_id: str,
    ) -> None:
        _ = request, command_id
        runtime = self._network_runtime_entries()
        if "worker" in runtime:
            raise RuntimeError("worker dispatcher is already running")
        app = _NetworkRuntimeApp(self, resolved, role="worker")
        dispatcher = WorkerDispatcher(app)
        app.dispatcher = dispatcher
        dispatcher.set_status_callback(
            lambda message: self._network_logger().info("Network worker: %s", message)
        )
        runtime["worker"] = {"app": app, "dispatcher": dispatcher}

    def stop_network_worker(
        self,
        *,
        resolved: ResolvedPaths,
        request: dict[str, Any],
        command_id: str,
    ) -> None:
        _ = resolved, request, command_id
        runtime = self._network_runtime_entries()
        entry = runtime.get("worker")
        if not entry:
            return
        app = entry.get("app")
        release_active_job = True
        if isinstance(app, _NetworkRuntimeApp):
            app.abort_current_worker_job("network worker stop")
            if app.has_active_worker_job() and not app.wait_for_active_process_exit(timeout_seconds=10.0):
                release_active_job = False
                self._network_logger().warning(
                    "Worker stop requested but the pipeline process is still running; keeping the coordinator claim until recovery/reclaim."
                )
        dispatcher = entry.get("dispatcher")
        try:
            shutdown = getattr(dispatcher, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown(release_active_job=release_active_job)
                except TypeError:
                    shutdown()
        finally:
            runtime.pop("worker", None)

    def _resolve_queue_refresh_interval(self, resolved: ResolvedPaths) -> float:
        config = dict(getattr(resolved, "config_data", {}) or {})
        try:
            interval = float(config.get("CoordinatorQueueRefreshSecs", COORDINATOR_QUEUE_REFRESH_SECONDS))
        except (TypeError, ValueError):
            interval = COORDINATOR_QUEUE_REFRESH_SECONDS
        return max(_MIN_QUEUE_REFRESH_SECONDS, interval)

    def _refresh_coordinator_queue_records(
        self,
        entry: dict[str, Any],
        resolved: ResolvedPaths,
        *,
        force_refresh: bool = True,
    ) -> bool:
        """Re-scan the source queue and swap it into the running app.

        Returns ``True`` when a fresh preview was loaded and applied. In-flight
        and recently-completed paths stay protected by the registry's claim
        guard and recent-completion grace window, so a refresh that still lists
        a claimed file cannot cause a double-claim.
        """
        app = entry.get("app")
        if not isinstance(app, _NetworkRuntimeApp):
            return False
        try:
            fresh = self._load_network_queue_records(resolved, force_refresh=force_refresh)
        except Exception as exc:
            self._network_logger().warning("Coordinator queue refresh failed: %s", exc)
            return False
        failures = self._load_network_failure_records(resolved)
        with app._queue_lock:
            app.queue_records = fresh
            app.failure_records = failures
        return True

    def _start_coordinator_queue_refresh_loop(
        self, entry: dict[str, Any], resolved: ResolvedPaths
    ) -> None:
        stop_event = threading.Event()
        entry["queue_refresh_stop"] = stop_event
        interval = self._resolve_queue_refresh_interval(resolved)

        def _loop() -> None:
            while not stop_event.wait(interval):
                self._refresh_coordinator_queue_records(entry, resolved)

        thread = threading.Thread(
            target=_loop,
            name="network-coordinator-queue-refresh",
            daemon=True,
        )
        entry["queue_refresh_thread"] = thread
        thread.start()

    def _start_coordinator_local_worker_loop(self, entry: dict[str, Any]) -> None:
        stop_event = threading.Event()
        entry["local_worker_stop"] = stop_event

        def _loop() -> None:
            while not stop_event.is_set():
                app = entry.get("app")
                dispatcher = entry.get("dispatcher")
                if not isinstance(app, _NetworkRuntimeApp) or dispatcher is None:
                    return
                if app.has_active_worker_job():
                    stop_event.wait(1.0)
                    continue
                try:
                    job = dispatcher.claim_next()
                except Exception as exc:
                    self._network_logger().warning("Coordinator local worker claim failed: %s", exc)
                    stop_event.wait(5.0)
                    continue
                if job is None:
                    stop_event.wait(5.0)
                    continue
                try:
                    app._start_claimed_encode(job, dispatcher)
                except Exception as exc:
                    self._network_logger().warning("Coordinator local worker start failed: %s", exc)
                    try:
                        dispatcher.release(job)
                    except Exception as release_exc:
                        self._network_logger().warning("Coordinator local worker release failed: %s", release_exc)
                    stop_event.wait(5.0)

        thread = threading.Thread(
            target=_loop,
            name="network-coordinator-local-worker",
            daemon=True,
        )
        entry["local_worker_thread"] = thread
        thread.start()

    def _start_network_claimed_job(self, app: _NetworkRuntimeApp, dispatcher: Any, job: Any) -> Any:
        _ = dispatcher
        source_path = str(getattr(getattr(job, "record", None), "source_path", "") or "").strip()
        if not source_path:
            raise RuntimeError("claimed network job has no source_path")
        launch_lock, lock_message = self._acquire_process_launch_lock("Network worker single-file start")
        if lock_message:
            raise RuntimeError(lock_message)
        try:
            block_message = self._active_work_block_message(app.resolved, "Pipeline start")
            if block_message:
                raise RuntimeError(block_message)
            runtime_prep = getattr(self.service, "prepare_pipeline_runtime_for_launch", None)
            if callable(runtime_prep):
                runtime_prep(app.resolved)
            control_prep = getattr(self.service, "prepare_pipeline_control_flags_for_launch", None)
            if callable(control_prep):
                control_prep(app.resolved)
            starter = getattr(self.service, "start_pipeline", None)
            if not callable(starter):
                raise RuntimeError("Pipeline start service is not available.")
            return starter(
                resolved=app.resolved,
                mode="once",
                show_config=False,
                sleep_seconds=1,
                extra_args="",
                show_console=False,
                single_file=source_path,
            )
        finally:
            self._release_process_launch_lock(launch_lock)


__all__ = ["NetworkLifecycleProviderMixin"]
