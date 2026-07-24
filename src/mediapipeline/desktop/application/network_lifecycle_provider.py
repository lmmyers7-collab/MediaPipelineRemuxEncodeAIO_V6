from __future__ import annotations

import json
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
    KEY_WORKER_ENCODER_MAP,
    KEY_WORKER_HONOR_COORDINATOR_POLICY,
    KEY_WORKER_SOURCE_PATH_MAP,
)
from mediapipeline.core.kernel.models import ResolvedPaths
from mediapipeline.core.network.url_policy import redact_network_secret_text
from mediapipeline.core.processes.pipeline_policy import coordinator_also_encode_locally_enabled
from mediapipeline.desktop.network.coordinator import CoordinatorDispatcher
from mediapipeline.desktop.network.failure_reasons import REASON_ENCODE_ERROR
from mediapipeline.desktop.network.processing_policy import materialize_worker_effective_config
from mediapipeline.desktop.network.registry import normalize_source_identity
from mediapipeline.desktop.network.worker import WorkerDispatcher
from mediapipeline.desktop.network.worker_state import atomic_write_text


_log = logging.getLogger(__name__)

# How often the coordinator re-scans the source queue so workers keep getting
# newly added media instead of draining only the start-time snapshot. Honoured
# via the optional CoordinatorQueueRefreshSecs config key; clamped to >= 5s.
COORDINATOR_QUEUE_REFRESH_SECONDS = 15.0
_MIN_QUEUE_REFRESH_SECONDS = 5.0
_NETWORK_WORKER_RESULT_ROOT = "NetworkWorkerResults"
_NETWORK_WORKER_SLOT_ID = 0
_RUNNING_WORKER_HOT_APPLY_KEYS = (
    KEY_WORKER_COORDINATOR_URL,
    KEY_WORKER_AUTH_TOKEN,
    KEY_WORKER_SOURCE_PATH_MAP,
    KEY_WORKER_ENCODER_MAP,
    KEY_WORKER_HONOR_COORDINATOR_POLICY,
)
_RUNNING_WORKER_HOT_APPLY_METHODS = {
    KEY_WORKER_COORDINATOR_URL: "update_coordinator_url",
    KEY_WORKER_AUTH_TOKEN: "update_auth_token",
    KEY_WORKER_SOURCE_PATH_MAP: "update_source_path_map",
    KEY_WORKER_ENCODER_MAP: "update_worker_encoder_map",
    KEY_WORKER_HONOR_COORDINATOR_POLICY: "update_honor_coordinator_policy",
}
_RUNNING_WORKER_CONNECTION_IDENTITY_KEYS = {
    KEY_WORKER_COORDINATOR_URL,
    KEY_WORKER_AUTH_TOKEN,
}


def _bounded_result_error(value: Any, *, limit: int = 500) -> str:
    text = redact_network_secret_text(value).replace("\r", " ").replace("\n", " ").strip()
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return text[: max(0, limit - 3)] + "..."


def _safe_machine_id() -> str:
    try:
        raw = socket.gethostname()
    except Exception:
        raw = ""
    machine_id = re.sub(r"[^A-Za-z0-9._-]+", "-", str(raw or "").strip()).strip(".-_")
    return (machine_id or f"worker-{uuid.uuid4().hex[:12]}")[:64]


def _runtime_state_dir(resolved: ResolvedPaths) -> Path:
    app_state_path = getattr(resolved, "app_state_path", None)
    if app_state_path:
        return Path(app_state_path).parent
    state_root = getattr(resolved, "state_root", None)
    if state_root is not None:
        return Path(state_root) / "App"
    return Path(getattr(resolved, "app_root", Path.cwd()))


def _safe_result_slug(value: Any) -> str:
    slug = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "").strip()).strip(".-_")
    return (slug or uuid.uuid4().hex)[:80]


def _network_worker_result_path(resolved: ResolvedPaths, job: Any, run_id: str) -> Path:
    job_slug = _safe_result_slug(getattr(job, "job_id", ""))
    return _runtime_state_dir(resolved) / _NETWORK_WORKER_RESULT_ROOT / job_slug / f"{run_id}.worker_result.json"


def _strict_bool_field(payload: dict[str, Any], key: str, *, default: bool | None = None) -> bool:
    if key not in payload:
        if default is None:
            raise ValueError(f"worker result field {key} is required")
        return bool(default)
    value = payload.get(key)
    if not isinstance(value, bool):
        raise ValueError(f"worker result field {key} must be a boolean")
    return value


def _nonnegative_int_field(payload: dict[str, Any], key: str, *, default: int = 0) -> int:
    if key not in payload:
        return default
    value = payload[key]
    if type(value) is not int:
        raise ValueError(f"worker result field {key} must be a nonnegative integer")
    if value < 0:
        raise ValueError(f"worker result field {key} must be a nonnegative integer")
    return value


def _network_worker_result_identity(proc: Any) -> tuple[Path | None, str, str]:
    raw_path = str(getattr(proc, "_network_worker_result_path", "") or "").strip()
    run_id = str(getattr(proc, "_network_worker_run_id", "") or "").strip()
    claim_id = str(getattr(proc, "_network_worker_claim_id", "") or "").strip()
    return (Path(raw_path) if raw_path else None), run_id, claim_id


def _network_job_metadata(job: Any) -> dict[str, Any]:
    metadata = getattr(job, "claim_metadata", None)
    if isinstance(metadata, dict):
        return dict(metadata)
    encode_config = getattr(job, "encode_config", {}) or {}
    embedded = encode_config.get("__claim_metadata") if isinstance(encode_config, dict) else None
    return dict(embedded) if isinstance(embedded, dict) else {}


def _augment_network_worker_result(payload: dict[str, Any], job: Any) -> dict[str, Any]:
    metadata = _network_job_metadata(job)
    if str(metadata.get("job_kind") or "") != "csv_rerun_row":
        return payload
    augmented = dict(payload)
    augmented["JobKind"] = "csv_rerun_row"
    augmented["RerunBatchId"] = str(metadata.get("rerun_batch_id") or "")
    augmented["RerunRowKey"] = str(metadata.get("rerun_row_key") or "")
    augmented["RerunRowIndex"] = int(metadata.get("rerun_row_index") or 0)
    augmented["PlannedOutputPath"] = str(metadata.get("planned_output_path") or "")
    augmented["CoordinatorSourcePath"] = str(metadata.get("coordinator_source_path") or "")
    augmented["WorkerSourcePath"] = str(metadata.get("worker_source_path") or "")
    augmented["DestinationPolicyApplied"] = False
    augmented["NetworkRerun"] = {
        "batch_id": augmented["RerunBatchId"],
        "row_key": augmented["RerunRowKey"],
        "row_index": augmented["RerunRowIndex"],
        "planned_output_path": augmented["PlannedOutputPath"],
        "output_handoff": dict(metadata.get("output_handoff") or {}),
        "source_identity": dict(metadata.get("source_identity") or {}),
        "coordinator_source_path": augmented["CoordinatorSourcePath"],
        "worker_source_path": augmented["WorkerSourcePath"],
        "handoff_probe": dict(metadata.get("handoff_probe") or {}),
        "destination_policy_applied": False,
    }
    return augmented


def _worker_result_enrichment_evidence(
    *,
    status: str,
    error: str = "",
    artifact_preserved: bool = True,
) -> dict[str, Any]:
    return {
        "schema_version": "network_worker_result_enrichment.v1",
        "status": status,
        "error": error,
        "artifact_preserved": artifact_preserved,
    }


def _read_network_worker_result(proc: Any, job: Any) -> tuple[dict[str, Any] | None, str, dict[str, Any]]:
    not_attempted = _worker_result_enrichment_evidence(status="not_attempted")
    result_path, expected_run_id, expected_claim_id = _network_worker_result_identity(proc)
    if result_path is None:
        return None, "network worker result artifact path was not attached", not_attempted
    if not result_path.exists():
        return None, f"network worker result artifact is missing: {result_path}", not_attempted
    try:
        payload = json.loads(result_path.read_text(encoding="utf-8-sig"))
    except Exception as exc:
        return None, f"network worker result artifact could not be read: {_bounded_result_error(exc)}", not_attempted
    if not isinstance(payload, dict):
        return None, "network worker result artifact root must be a JSON object", not_attempted
    if str(payload.get("SchemaVersion") or "") != "local_worker_result.v1":
        return None, "network worker result artifact schema is not local_worker_result.v1", not_attempted
    actual_claim_id = str(payload.get("WorkerClaimId") or "")
    job_id = str(getattr(job, "job_id", "") or "")
    if actual_claim_id != expected_claim_id or actual_claim_id != job_id:
        return None, "network worker result artifact claim id does not match the active claim", not_attempted
    if str(payload.get("WorkerRunId") or "") != expected_run_id:
        return None, "network worker result artifact run id does not match the launched run", not_attempted
    try:
        _strict_bool_field(payload, "Success")
        _strict_bool_field(payload, "QueueTerminal", default=False)
        _strict_bool_field(payload, "Retryable", default=True)
        _nonnegative_int_field(payload, "ElapsedSeconds", default=0)
        _nonnegative_int_field(payload, "OutputSizeBytes", default=0)
    except ValueError as exc:
        return None, str(exc), not_attempted
    try:
        augmented = _augment_network_worker_result(payload, job)
        if augmented is payload:
            return payload, "", _worker_result_enrichment_evidence(status="not_required")
        serialized = json.dumps(augmented, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    except Exception as exc:
        enrichment_error = f"network worker rerun metadata could not be built: {_bounded_result_error(exc)}"
        return payload, "", _worker_result_enrichment_evidence(status="failed", error=enrichment_error)
    try:
        atomic_write_text(result_path, serialized)
    except Exception as exc:
        enrichment_error = f"network worker rerun metadata could not be persisted atomically: {_bounded_result_error(exc)}"
        return augmented, "", _worker_result_enrichment_evidence(status="failed", error=enrichment_error)
    return augmented, "", _worker_result_enrichment_evidence(status="persisted")


def _network_done_kwargs_from_result(
    proc: Any,
    job: Any,
    *,
    return_code: int | None,
    wait_error: str,
    elapsed_seconds: float,
) -> dict[str, Any]:
    result_path, _expected_run_id, _expected_claim_id = _network_worker_result_identity(proc)
    artifact_path = str(result_path or "")
    result, result_error, enrichment = _read_network_worker_result(proc, job)
    process_error = wait_error
    if return_code != 0 and not process_error:
        process_error = f"pipeline process exited with code {return_code}"
    if result is None:
        detail = result_error or process_error or "network worker result artifact is unavailable"
        return {
            "success": False,
            "error": detail,
            "elapsed_seconds": elapsed_seconds,
            "completion_status": "failed_result_missing" if "missing" in detail.lower() else "failed_result_invalid",
            "route": "network_lifecycle_single_file",
            "queue_terminal": False,
            "retry_on_failure": True,
            "reason_code": REASON_ENCODE_ERROR,
            "reason": detail,
            "worker_result_artifact": {},
            "worker_result_artifact_path": artifact_path,
        }

    artifact_success = _strict_bool_field(result, "Success")
    queue_terminal = _strict_bool_field(result, "QueueTerminal", default=False)
    retryable = _strict_bool_field(result, "Retryable", default=True)
    status = str(result.get("Status") or "").strip()
    reason = str(result.get("Reason") or "").strip()
    success = artifact_success and not process_error
    metadata = _network_job_metadata(job)
    job_kind = str(metadata.get("job_kind") or "pipeline_queue")
    publish_state = str(result.get("PublishState") or "")
    if job_kind == "csv_rerun_row" and success and "pending" in publish_state.casefold():
        success = False
        reason = (
            "Network CSV rerun worker produced worker-owned pending publish state; "
            "only handoff output is accepted before coordinator reduction."
        )
        status = "failed_worker_pending_publish_not_accepted"
        queue_terminal = False
        retryable = True
    if not success and not reason:
        reason = process_error or status or "network worker process failed"
    result_artifact = dict(result)
    result_artifact["CoordinatorMetadataPersistence"] = dict(enrichment)
    if enrichment.get("status") == "failed":
        _log.warning("Network worker result metadata enrichment failed: %s", enrichment.get("error") or "unknown error")
    return {
        "success": success,
        "output_path": str(result.get("OutputPath") or ""),
        "error": "" if success else (process_error or reason),
        "elapsed_seconds": elapsed_seconds,
        "output_size_bytes": _nonnegative_int_field(result, "OutputSizeBytes", default=0),
        "completion_status": status or ("processed" if success else "failed"),
        "publish_state": publish_state,
        "publish_mode": str(result.get("PublishMode") or ""),
        "route": str(result.get("Route") or "network_lifecycle_single_file"),
        "queue_terminal": queue_terminal,
        "retry_on_failure": retryable,
        "reason_code": str(result.get("ErrorCode") or ("" if success else REASON_ENCODE_ERROR)),
        "reason": "" if success else reason,
        "worker_result_artifact": result_artifact,
        "worker_result_artifact_path": artifact_path,
    }


def _entry_has_active_network_job(entry: dict[str, Any]) -> bool:
    app = entry.get("app")
    if isinstance(app, _NetworkRuntimeApp) and app.has_active_worker_job():
        return True
    dispatcher = entry.get("dispatcher")
    get_active_job = getattr(dispatcher, "get_active_job", None)
    if callable(get_active_job):
        try:
            if get_active_job() is not None:
                return True
        except Exception:
            return True
    active_claims_snapshot = getattr(dispatcher, "active_claims_snapshot", None)
    if callable(active_claims_snapshot):
        try:
            return len(list(active_claims_snapshot() or [])) > 0
        except Exception:
            return True
    coordinator_stats = getattr(dispatcher, "coordinator_stats", None)
    if callable(coordinator_stats):
        try:
            stats = coordinator_stats() or {}
            return int(stats.get("active") or 0) > 0
        except Exception:
            return True
    return False


def _join_coordinator_provider_threads(entry: dict[str, Any], *, timeout: float = 5.0) -> None:
    for thread_key in ("local_worker_thread", "queue_refresh_thread"):
        thread = entry.get(thread_key)
        if isinstance(thread, threading.Thread) and thread is not threading.current_thread():
            thread.join(timeout=timeout)


def _shutdown_coordinator_dispatcher(dispatcher: Any) -> None:
    shutdown = getattr(dispatcher, "shutdown", None)
    if callable(shutdown):
        shutdown()


def _shutdown_worker_dispatcher(dispatcher: Any) -> None:
    shutdown = getattr(dispatcher, "shutdown", None)
    if callable(shutdown):
        try:
            shutdown(release_active_job=False, preserve_active_job=True)
        except TypeError:
            shutdown()


class _ImmediateCallbackRoot:
    def after(self, _delay_ms: int, callback: Any, *args: Any) -> None:
        if callable(callback):
            callback(*args)


class _NetworkRuntimeApp:
    def __init__(self, facade: object, resolved: ResolvedPaths, *, role: str) -> None:
        self.facade = facade
        self.service = facade.service
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
        target_identity = normalize_source_identity(target)
        with self._queue_lock:
            self.queue_records = [
                record
                for record in self.queue_records
                if normalize_source_identity(getattr(record, "source_path", "") or "") != target_identity
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
                done_kwargs = _network_done_kwargs_from_result(
                    proc,
                    job,
                    return_code=return_code,
                    wait_error=error_text,
                    elapsed_seconds=elapsed,
                )
                try:
                    dispatcher.mark_done(job, **done_kwargs)
                except Exception as exc:
                    _log.warning("Network worker done report failed for job %s: %s", getattr(job, "job_id", ""), exc)
                with self._active_lock:
                    if self._active_job is job:
                        self._active_job = None
                        self._active_proc = None
                finisher = getattr(self.facade, "_network_active_job_finished", None)
                if callable(finisher):
                    finisher(role=self.role, app=self)

        thread = threading.Thread(
            target=_watch,
            name="network-worker-process-watch",
            daemon=True,
        )
        try:
            thread.start()
        except Exception as exc:
            error_text = f"network worker process watcher failed to start: {exc}"
            _log.error("Network worker process watcher failed for job %s: %s", getattr(job, "job_id", ""), exc)
            try:
                self.abort_current_worker_job("network worker process watcher failed to start")
            except Exception as abort_exc:
                _log.warning("Network worker process cleanup failed for job %s: %s", getattr(job, "job_id", ""), abort_exc)
            try:
                dispatcher.mark_done(
                    job,
                    success=False,
                    error=error_text,
                    elapsed_seconds=max(0.0, time.monotonic() - started_at),
                    completion_status="failed",
                    route="network_lifecycle_single_file",
                    queue_terminal=False,
                )
            except Exception as done_exc:
                _log.warning("Network worker failed-done report failed for job %s: %s", getattr(job, "job_id", ""), done_exc)
            with self._active_lock:
                if self._active_job is job:
                    self._active_job = None
                    self._active_proc = None
            finisher = getattr(self.facade, "_network_active_job_finished", None)
            if callable(finisher):
                finisher(role=self.role, app=self)
            return

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
            self._network_dispatcher_runtime = runtime
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

        active_claim = _entry_has_active_network_job(entry)
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
                update = {
                    "schema_version": "desktop_network_worker_hot_apply.v1",
                    "role": "worker",
                    "key": key,
                    "status": "applied",
                    "method": method_name,
                }
                if active_claim and key in _RUNNING_WORKER_CONNECTION_IDENTITY_KEYS:
                    update.update(
                        {
                            "active_claim_affinity": "preserved",
                            "message": (
                                "Saved connection identity applies to idle/future requests; "
                                "the active claim remains bound to its issuing coordinator."
                            ),
                        }
                    )
                updates.append(update)

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
        dispatcher: Any = None
        entry: dict[str, Any] = {"app": app}
        try:
            app.queue_records = self._load_network_queue_records(resolved)
            app.failure_records = self._load_network_failure_records(resolved)
            dispatcher = CoordinatorDispatcher(app)
            app.dispatcher = dispatcher
            entry["dispatcher"] = dispatcher
            # Keep the served queue live so newly added media is distributed
            # instead of only the start-time snapshot draining to idle.
            self._start_coordinator_queue_refresh_loop(entry, resolved)
            if coordinator_also_encode_locally_enabled(resolved.config_data or {}):
                self._start_coordinator_local_worker_loop(entry)
            runtime["coordinator"] = entry
        except Exception:
            queue_refresh_stop = entry.get("queue_refresh_stop")
            if isinstance(queue_refresh_stop, threading.Event):
                queue_refresh_stop.set()
            stop_event = entry.get("local_worker_stop")
            if isinstance(stop_event, threading.Event):
                stop_event.set()
            if dispatcher is not None:
                try:
                    _shutdown_coordinator_dispatcher(dispatcher)
                finally:
                    _join_coordinator_provider_threads(entry)
            if runtime.get("coordinator") is entry:
                runtime.pop("coordinator", None)
            raise

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
        active_network_work = _entry_has_active_network_job(entry)
        dispatcher = entry.get("dispatcher")
        if active_network_work:
            entry["stop_requested"] = True
            self._network_logger().warning(
                "Coordinator stop requested with active network work; stopping new claims and preserving reporting routes until work is terminal."
            )
            begin_drain = getattr(dispatcher, "begin_drain", None)
            if callable(begin_drain):
                begin_drain()
            else:
                _shutdown_coordinator_dispatcher(dispatcher)
            _join_coordinator_provider_threads(entry)
            if not self._finalize_coordinator_drain_if_idle(entry):
                self._start_coordinator_drain_monitor(entry)
            return
        try:
            _shutdown_coordinator_dispatcher(dispatcher)
        finally:
            _join_coordinator_provider_threads(entry)
            runtime.pop("coordinator", None)

    def _finalize_coordinator_drain_if_idle(self, entry: dict[str, Any]) -> bool:
        runtime = self._network_runtime_entries()
        if runtime.get("coordinator") is not entry:
            return True
        if not entry.get("stop_requested"):
            return False
        if _entry_has_active_network_job(entry):
            return False
        drain_stop = entry.get("drain_monitor_stop")
        if isinstance(drain_stop, threading.Event):
            drain_stop.set()
        dispatcher = entry.get("dispatcher")
        try:
            _shutdown_coordinator_dispatcher(dispatcher)
        finally:
            _join_coordinator_provider_threads(entry)
            if runtime.get("coordinator") is entry:
                runtime.pop("coordinator", None)
        return True

    def _start_coordinator_drain_monitor(self, entry: dict[str, Any]) -> None:
        existing = entry.get("drain_monitor_thread")
        if isinstance(existing, threading.Thread) and existing.is_alive():
            return
        stop_event = threading.Event()
        entry["drain_monitor_stop"] = stop_event

        def _monitor() -> None:
            while not stop_event.wait(0.25):
                try:
                    if self._finalize_coordinator_drain_if_idle(entry):
                        return
                except Exception as exc:
                    self._network_logger().warning("Coordinator drain monitor failed: %s", exc)
                    return

        thread = threading.Thread(
            target=_monitor,
            name="network-coordinator-drain-monitor",
            daemon=True,
        )
        entry["drain_monitor_thread"] = thread
        thread.start()

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
        try:
            dispatcher = WorkerDispatcher(app, start_polling=False)
            start_polling_after_attach = True
        except TypeError:
            dispatcher = WorkerDispatcher(app)
            start_polling_after_attach = False
        app.dispatcher = dispatcher
        dispatcher.set_status_callback(
            lambda message: self._network_logger().info("Network worker: %s", message)
        )
        entry = {"app": app, "dispatcher": dispatcher}
        runtime["worker"] = entry
        try:
            if start_polling_after_attach:
                start_polling = getattr(dispatcher, "start_polling", None)
                if callable(start_polling):
                    start_polling()
        except Exception:
            try:
                _shutdown_worker_dispatcher(dispatcher)
            finally:
                if runtime.get("worker") is entry:
                    runtime.pop("worker", None)
            raise

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
        active_job = _entry_has_active_network_job(entry)
        if active_job:
            entry["stop_requested"] = True
            self._network_logger().warning(
                "Worker stop requested with an active job; stopping polling and preserving the active process for done reporting."
            )
        dispatcher = entry.get("dispatcher")
        try:
            shutdown = getattr(dispatcher, "shutdown", None)
            if callable(shutdown):
                try:
                    shutdown(release_active_job=not active_job, preserve_active_job=active_job)
                except TypeError:
                    shutdown()
        finally:
            if not active_job:
                runtime.pop("worker", None)

    def _network_active_job_finished(self, *, role: str, app: _NetworkRuntimeApp) -> None:
        runtime = self._network_runtime_entries()
        entry = runtime.get(role)
        if not isinstance(entry, dict) or entry.get("app") is not app:
            return
        if not entry.get("stop_requested"):
            return
        if app.has_active_worker_job():
            return
        if role == "coordinator":
            self._finalize_coordinator_drain_if_idle(entry)
            return
        runtime.pop(role, None)

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
            launch_resolved, policy_evidence = materialize_worker_effective_config(app.resolved, job=job)
            if policy_evidence.get("status") == "applied":
                self._network_logger().info(
                    "Network worker using coordinator policy for job %s: family=%s encoder=%s quality=%s config=%s",
                    str(getattr(job, "job_id", ""))[:8],
                    policy_evidence.get("target_codec_family"),
                    policy_evidence.get("local_encoder"),
                    policy_evidence.get("quality_value"),
                    policy_evidence.get("config_path"),
                )
            elif _network_job_metadata(job).get("job_kind") == "csv_rerun_row":
                raise RuntimeError(
                    "Network CSV rerun worker job cannot start without applied handoff config: "
                    f"{policy_evidence.get('reason') or policy_evidence.get('status') or 'unknown'}"
                )
            result_run_id = uuid.uuid4().hex
            result_path = _network_worker_result_path(launch_resolved, job, result_run_id)
            result_path.parent.mkdir(parents=True, exist_ok=True)
            extra_argv = [
                "-WorkerChild",
                "-WorkerSlotId",
                str(_NETWORK_WORKER_SLOT_ID),
                "-WorkerRunId",
                result_run_id,
                "-WorkerClaimId",
                str(getattr(job, "job_id", "") or ""),
                "-WorkerResultPath",
                str(result_path),
            ]
            proc = starter(
                resolved=launch_resolved,
                mode="once",
                show_config=False,
                sleep_seconds=1,
                extra_args="",
                extra_argv=extra_argv,
                show_console=False,
                single_file=source_path,
            )
            try:
                proc._network_worker_result_path = str(result_path)
                proc._network_worker_run_id = result_run_id
                proc._network_worker_claim_id = str(getattr(job, "job_id", "") or "")
            except Exception:
                self._network_logger().warning("Network worker result metadata could not be attached to process object.")
            return proc
        finally:
            self._release_process_launch_lock(launch_lock)


__all__ = ["NetworkLifecycleProviderMixin"]
