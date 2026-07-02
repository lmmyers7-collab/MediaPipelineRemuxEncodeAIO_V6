from __future__ import annotations

import os
import queue
import threading
import time
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path
from typing import Any

from mediapipeline.core.processes.pipeline_policy import (
    configured_network_role,
    network_role_blocks_normal_launch,
    network_role_is_valid,
)

from .scanner import FileStat, FiredRegistry, ScanError, ScanResult, StabilityTracker, normalize_extensions, scan_root


WATCH_POLL_INTERVAL_SECONDS = 10.0
WATCH_FOLDERS_SCHEMA_VERSION = "desktop_watch_folders.v1"


@dataclass(frozen=True)
class WatchContext:
    load_settings: Callable[[], Mapping[str, Any]]
    default_watch_roots: Callable[[], list[str]]
    start_pipeline: Callable[[dict[str, Any]], Any]
    log: Callable[[str], None]


def _utc_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().casefold() in {"1", "true", "yes", "on"}


def _setting_int(settings: Mapping[str, Any], key: str, default: int) -> int:
    try:
        return int(settings.get(key, default) or default)
    except (TypeError, ValueError):
        return int(default)


def _string_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [item.strip() for item in value.replace("\n", ",").split(",") if item.strip()]
    try:
        return [str(item).strip() for item in value if str(item).strip()]
    except TypeError:
        text = str(value).strip()
    return [text] if text else []


def _canonical_path(path: str) -> str:
    try:
        return str(Path(path).expanduser().resolve(strict=False))
    except (OSError, RuntimeError, ValueError):
        return os.path.abspath(os.path.expanduser(path))


def _normalize_roots(roots: list[str]) -> list[str]:
    normalized: list[str] = []
    seen: set[str] = set()
    for root in roots:
        text = str(root or "").strip()
        if not text:
            continue
        absolute = _canonical_path(text)
        key = _path_key(absolute)
        if key in seen:
            continue
        seen.add(key)
        normalized.append(absolute)
    return normalized


def _snapshot_signature(roots: list[str], extensions: frozenset[str]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    root_keys = tuple(_path_key(root) for root in roots)
    return root_keys, tuple(sorted(extensions))


def _path_key(path: str) -> str:
    return os.path.normcase(_canonical_path(path)).casefold()


def _result_message(result: Any) -> str:
    if isinstance(result, Mapping):
        return str(result.get("message") or "")
    return str(getattr(result, "message", "") or "")


def _result_ok(result: Any) -> bool:
    if isinstance(result, Mapping):
        return bool(result.get("ok", False))
    return bool(getattr(result, "ok", False))


def _result_data(result: Any) -> Mapping[str, Any]:
    if isinstance(result, Mapping):
        data = result.get("data")
    else:
        data = getattr(result, "data", None)
    return data if isinstance(data, Mapping) else {}


class WatchFolderManager:
    def __init__(self, *, poll_interval_seconds: float = WATCH_POLL_INTERVAL_SECONDS) -> None:
        self._poll_interval_seconds = max(0.05, float(poll_interval_seconds))
        self._lock = threading.Lock()
        self._stop_event: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self._context: WatchContext | None = None
        self._last_settings: dict[str, Any] = {}
        self._baseline_signature: tuple[tuple[str, ...], tuple[str, ...]] | None = None
        self._baseline_stats: dict[str, FileStat] = {}
        self._tracker = StabilityTracker(debounce_seconds=30.0)
        self._fired = FiredRegistry()
        self._scan_threads: dict[str, threading.Thread] = {}
        self._recent_detections: list[dict[str, str]] = []
        self._state: dict[str, Any] = self._default_state()

    def _default_state(self) -> dict[str, Any]:
        return {
            "schema_version": WATCH_FOLDERS_SCHEMA_VERSION,
            "enabled": False,
            "running": False,
            "effective_action": "enqueue_only",
            "network_role": "standalone",
            "roots": [],
            "derived_roots_from_library_profiles": False,
            "debounce_seconds": 30,
            "scan_timeout_seconds": 300,
            "pending_work": False,
            "recent_detections": [],
            "last_launch": None,
            "last_refusal": None,
            "last_cycle_completed_utc": "",
            "last_error": "",
            "status": "idle",
            "reason": "Watch-folder manager has not started.",
        }

    def available(self) -> bool:
        return True

    def start(self, context: WatchContext) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                self._context = context
                self._state["running"] = True
                return
            stop_event = threading.Event()
            self._context = context
            self._stop_event = stop_event
            self._state["running"] = True
            self._state["status"] = "running"
            self._state["reason"] = "Watch-folder manager started."
        try:
            self.run_single_cycle()
        except Exception as exc:
            self._record_error(f"Watch-folder startup cycle failed: {exc}")
        thread = threading.Thread(
            target=self._run,
            name="MediaPipelineWatchFolders",
            daemon=True,
            args=(stop_event,),
        )
        with self._lock:
            self._thread = thread
        thread.start()

    def stop(self, reason: str) -> None:
        with self._lock:
            stop_event = self._stop_event
            thread = self._thread
            self._stop_event = None
            self._thread = None
            self._state["running"] = False
            self._state["status"] = "stopped"
            self._state["reason"] = str(reason or "watch-folder manager stopped")
        if stop_event is not None:
            stop_event.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout=2.0)

    def state_mapping(self) -> dict[str, Any]:
        with self._lock:
            state = dict(self._state)
            state["roots"] = [dict(root) for root in state.get("roots") or []]
            state["recent_detections"] = [dict(row) for row in self._recent_detections]
            state["last_launch"] = dict(state["last_launch"]) if isinstance(state.get("last_launch"), dict) else None
            state["last_refusal"] = dict(state["last_refusal"]) if isinstance(state.get("last_refusal"), dict) else None
        return state

    def _run(self, stop_event: threading.Event) -> None:
        while not stop_event.wait(self._poll_interval_seconds):
            try:
                self.run_single_cycle()
            except Exception as exc:
                self._record_error(f"Watch-folder cycle failed: {exc}")

    def _record_error(self, message: str) -> None:
        with self._lock:
            self._state["last_error"] = message
            self._state["status"] = "degraded"
            self._state["reason"] = message
            self._state["last_cycle_completed_utc"] = _utc_now()

    def _load_settings(self, context: WatchContext) -> tuple[dict[str, Any], str]:
        try:
            settings = dict(context.load_settings() or {})
        except Exception as exc:
            return {
                "EnableWatchFolders": False,
                "NetworkRole": "__settings_reload_failed__",
                "WatchAction": "enqueue_only",
            }, f"settings reload failed; watch-folder launch suppressed: {exc}"
        self._last_settings = dict(settings)
        return settings, ""

    def _reset_baseline(self, signature: tuple[tuple[str, ...], tuple[str, ...]], snapshot: dict[str, FileStat]) -> None:
        self._baseline_signature = signature
        self._baseline_stats = {_path_key(path): stat for path, stat in snapshot.items()}
        self._tracker = StabilityTracker(debounce_seconds=self._tracker.debounce_seconds)
        with self._lock:
            self._state["pending_work"] = False

    def _scan_root_bounded(self, root: str, extensions: frozenset[str], timeout_seconds: int) -> ScanResult:
        root_key = _path_key(root)
        with self._lock:
            existing = self._scan_threads.get(root_key)
            if existing is not None and existing.is_alive():
                return ScanResult(
                    root=root,
                    snapshot={},
                    errors=(
                        ScanError(
                            path=root,
                            message="previous watch-folder scan is still running; skipping overlapping scan",
                        ),
                    ),
                )
            if existing is not None:
                self._scan_threads.pop(root_key, None)

        result_queue: queue.Queue[ScanResult | BaseException] = queue.Queue(maxsize=1)

        def worker() -> None:
            try:
                result_queue.put(scan_root(root, extensions))
            except BaseException as exc:  # pragma: no cover - defensive against filesystem scanner surprises
                result_queue.put(exc)

        thread = threading.Thread(
            target=worker,
            name=f"MediaPipelineWatchScan:{root_key[:48]}",
            daemon=True,
        )
        with self._lock:
            self._scan_threads[root_key] = thread
        thread.start()
        thread.join(timeout=max(0.001, float(timeout_seconds)))
        if thread.is_alive():
            return ScanResult(
                root=root,
                snapshot={},
                errors=(
                    ScanError(
                        path=root,
                        message=f"watch-folder scan timed out after {timeout_seconds} seconds",
                    ),
                ),
            )
        with self._lock:
            if self._scan_threads.get(root_key) is thread:
                self._scan_threads.pop(root_key, None)
        try:
            outcome = result_queue.get_nowait()
        except queue.Empty:
            return ScanResult(
                root=root,
                snapshot={},
                errors=(ScanError(path=root, message="watch-folder scan finished without returning a result"),),
            )
        if isinstance(outcome, BaseException):
            return ScanResult(root=root, snapshot={}, errors=(ScanError(path=root, message=str(outcome)),))
        return outcome

    def _update_state(
        self,
        *,
        enabled: bool,
        effective_action: str,
        network_role: str,
        roots: list[dict[str, Any]],
        derived_roots: bool,
        debounce_seconds: int,
        scan_timeout_seconds: int,
        pending_work: bool,
        status: str,
        reason: str,
        last_error: str,
    ) -> None:
        with self._lock:
            self._state.update(
                {
                    "enabled": bool(enabled),
                    "running": self._stop_event is not None and not self._stop_event.is_set(),
                    "effective_action": effective_action,
                    "network_role": network_role,
                    "roots": [dict(root) for root in roots],
                    "derived_roots_from_library_profiles": bool(derived_roots),
                    "debounce_seconds": int(debounce_seconds),
                    "scan_timeout_seconds": int(scan_timeout_seconds),
                    "pending_work": bool(pending_work),
                    "status": status,
                    "reason": reason,
                    "last_error": last_error,
                    "last_cycle_completed_utc": _utc_now(),
                }
            )

    def run_single_cycle(self, now: float | None = None) -> None:
        timestamp = time.monotonic() if now is None else float(now)
        context = self._context
        if context is None:
            self._record_error("Watch-folder manager has no context.")
            return

        settings, settings_warning = self._load_settings(context)
        network_role = configured_network_role(settings)
        network_role_valid = network_role_is_valid(network_role)
        enabled = _truthy(settings.get("EnableWatchFolders"))
        configured_action = str(settings.get("WatchAction") or "enqueue_only").strip().casefold()
        if configured_action not in {"enqueue_only", "enqueue_and_launch"}:
            configured_action = "enqueue_only"
        network_mode_active = network_role_blocks_normal_launch(network_role)
        effective_action = "enqueue_only" if network_mode_active else configured_action
        scan_timeout_seconds = max(1, _setting_int(settings, "WatchScanTimeoutSeconds", 300))

        if not enabled or network_role == "worker":
            reason = (
                "Watch folders disabled by settings."
                if not enabled
                else "Watch folders disabled while NetworkRole=worker; worker claims must come from a coordinator."
            )
            self._update_state(
                enabled=False,
                effective_action=effective_action,
                network_role=network_role,
                roots=[],
                derived_roots=False,
                debounce_seconds=max(5, _setting_int(settings, "WatchDebounceSeconds", 30)),
                scan_timeout_seconds=scan_timeout_seconds,
                pending_work=bool(self._state.get("pending_work", False)),
                status="idle",
                reason=settings_warning or reason,
                last_error=settings_warning,
            )
            return

        raw_roots = _string_list(settings.get("WatchFolderRoots"))
        derived_roots = not raw_roots
        if derived_roots:
            try:
                raw_roots = context.default_watch_roots()
            except Exception as exc:
                self._update_state(
                    enabled=True,
                    effective_action=effective_action,
                    network_role=network_role,
                    roots=[],
                    derived_roots=True,
                    debounce_seconds=max(5, _setting_int(settings, "WatchDebounceSeconds", 30)),
                    scan_timeout_seconds=scan_timeout_seconds,
                    pending_work=bool(self._state.get("pending_work", False)),
                    status="degraded",
                    reason=f"default watch roots unavailable: {exc}",
                    last_error=str(exc),
                )
                return
        roots = _normalize_roots(raw_roots)
        debounce = _setting_int(settings, "WatchDebounceSeconds", 0) or _setting_int(settings, "FileStabilityWait", 30)
        debounce = max(5, int(debounce))
        self._tracker.set_debounce_seconds(debounce)
        extensions = normalize_extensions(settings.get("ValidExtensions") or [])
        signature = _snapshot_signature(roots, extensions)

        root_states: list[dict[str, Any]] = []
        combined_snapshot: dict[str, FileStat] = {}
        root_errors: list[str] = []
        for root in roots:
            result = self._scan_root_bounded(root, extensions, scan_timeout_seconds)
            combined_snapshot.update(result.snapshot)
            error_text = "; ".join(error.message for error in result.errors[:3])
            root_exists = os.path.isdir(root)
            reachable = root_exists and not (not result.snapshot and result.errors)
            root_states.append(
                {
                    "path": root,
                    "reachable": bool(reachable),
                    "last_error": error_text,
                }
            )
            if error_text:
                root_errors.append(f"{root}: {error_text}")

        if self._baseline_signature != signature:
            self._reset_baseline(signature, combined_snapshot)
            self._update_state(
                enabled=True,
                effective_action=effective_action,
                network_role=network_role,
                roots=root_states,
                derived_roots=derived_roots,
                debounce_seconds=debounce,
                scan_timeout_seconds=scan_timeout_seconds,
                pending_work=False,
                status="running" if not (settings_warning or root_errors) else "degraded",
                reason=settings_warning or "Baseline snapshot recorded; future changes can trigger watch work.",
                last_error=settings_warning or "; ".join(root_errors),
            )
            return

        candidate_paths: set[str] = set()
        for path, stat in combined_snapshot.items():
            key = _path_key(path)
            baseline_stat = self._baseline_stats.get(key)
            if baseline_stat == stat:
                continue
            candidate_paths.add(path)
            self._tracker.observe(path, stat, timestamp)
        self._tracker.remove_missing(candidate_paths)

        stable_paths = self._tracker.pop_stable(timestamp)
        detected_utc = _utc_now()
        new_detections: list[dict[str, str]] = []
        for path, stat in stable_paths:
            if not self._fired.should_fire(path, stat, timestamp):
                continue
            new_detections.append({"path": path, "detected_utc": detected_utc})
        detected = len(new_detections)

        with self._lock:
            self._recent_detections.extend(new_detections)
            if len(self._recent_detections) > 50:
                self._recent_detections = self._recent_detections[-50:]
            pending_work = bool(self._state.get("pending_work", False) or detected)
            self._state["pending_work"] = pending_work

        last_error = settings_warning or "; ".join(root_errors)
        if pending_work and effective_action == "enqueue_and_launch":
            self._dispatch_launch(context, settings)
            with self._lock:
                pending_work = bool(self._state.get("pending_work", False))
        reason = (
            f"Detected {detected} stable file(s); normal Launch is blocked while NetworkRole={network_role}." if detected and network_mode_active else
            f"Detected {detected} stable file(s)." if detected else
            f"Pending watch work remains; normal Launch is blocked while NetworkRole={network_role}." if pending_work and network_mode_active else
            f"Pending watch work remains; invalid NetworkRole={network_role} keeps watch folders enqueue-only." if pending_work and not network_role_valid else
            "Pending watch work remains." if pending_work else
            "No new stable watch-folder files detected."
        )
        self._update_state(
            enabled=True,
            effective_action=effective_action,
            network_role=network_role,
            roots=root_states,
            derived_roots=derived_roots,
            debounce_seconds=debounce,
            scan_timeout_seconds=scan_timeout_seconds,
            pending_work=pending_work,
            status="running" if not last_error else "degraded",
            reason=settings_warning or reason,
            last_error=last_error,
        )

    def _dispatch_launch(self, context: WatchContext, settings: Mapping[str, Any]) -> None:
        requested_utc = _utc_now()
        network_role = configured_network_role(settings)
        if network_role_blocks_normal_launch(network_role):
            reason = f"Watch-folder launch suppressed while NetworkRole={network_role}; pending work remains enqueue-only."
            with self._lock:
                self._state["pending_work"] = True
                self._state["last_refusal"] = {"utc": requested_utc, "reason": reason}
                self._state["last_error"] = reason if not network_role_is_valid(network_role) else self._state.get("last_error", "")
            try:
                context.log(reason)
            except Exception:
                pass
            return
        request: dict[str, Any] = {
            "mode": "once",
            "sleep_seconds": 30,
            "show_config": False,
            "show_console": False,
            "extra_args": "",
        }
        if not _truthy(settings.get("WatchRespectScheduleWindow", True)):
            request["schedule_override"] = "ignore"
        try:
            result = context.start_pipeline(request)
        except Exception as exc:
            message = f"Watch-folder launch request failed: {exc}"
            with self._lock:
                self._state["pending_work"] = True
                self._state["last_error"] = message
                self._state["last_refusal"] = {"utc": requested_utc, "reason": message}
            return
        message = _result_message(result)
        if _result_ok(result):
            data = _result_data(result)
            pid = data.get("pid", "")
            with self._lock:
                self._state["pending_work"] = False
                self._state["last_launch"] = {
                    "requested_utc": requested_utc,
                    "outcome": "started",
                    "message": message,
                    "pid": pid,
                }
                self._state["last_refusal"] = None
            try:
                context.log(f"Watch-folder launch request succeeded: {message}")
            except Exception:
                pass
            return
        reason = message or "Watch-folder launch request was refused."
        with self._lock:
            self._state["pending_work"] = True
            self._state["last_refusal"] = {"utc": requested_utc, "reason": reason}
        try:
            context.log(f"Watch-folder launch request refused: {reason}")
        except Exception:
            pass


def watch_folder_state_mapping(watcher: object) -> dict[str, Any]:
    state_reader = getattr(watcher, "state_mapping", None)
    if not callable(state_reader):
        return WatchFolderManager().state_mapping() | {
            "status": "unavailable",
            "reason": "Watch-folder manager is not available.",
        }
    try:
        return dict(state_reader())
    except Exception as exc:
        return WatchFolderManager().state_mapping() | {
            "status": "error",
            "reason": "Watch-folder manager state could not be read.",
            "last_error": str(exc),
        }


__all__ = [
    "WATCH_FOLDERS_SCHEMA_VERSION",
    "WATCH_POLL_INTERVAL_SECONDS",
    "WatchContext",
    "WatchFolderManager",
    "watch_folder_state_mapping",
]
