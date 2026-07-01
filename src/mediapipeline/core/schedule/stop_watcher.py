from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from mediapipeline.core.paths.contracts import ResolvedPaths


@dataclass(frozen=True)
class ScheduleStopWatcherState:
    status: str = "idle"
    pid: int = 0
    deadline: str = ""
    stop_requested: bool = False
    generation: int = 0
    message: str = "No backend schedule-stop watcher is armed."
    error: str = ""

    def to_mapping(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "pid": self.pid,
            "deadline": self.deadline,
            "stop_requested": self.stop_requested,
            "generation": self.generation,
            "message": self.message,
            "error": self.error,
        }


def parse_schedule_stop_deadline(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value
    text = str(value or "").strip()
    if not text or text.casefold() == "none":
        return None
    try:
        return datetime.fromisoformat(text)
    except ValueError:
        return None


def schedule_stop_deadline_from_gate(schedule_gate: dict[str, Any]) -> datetime | None:
    data = schedule_gate.get("data") if isinstance(schedule_gate.get("data"), dict) else {}
    return parse_schedule_stop_deadline(data.get("current_window_end"))


def _now_for_deadline(deadline: datetime) -> datetime:
    return datetime.now(deadline.tzinfo) if deadline.tzinfo is not None else datetime.now()


class ScheduleStopWatcherManager:
    """Backend-owned watcher that requests Stop After Current at a schedule boundary."""

    def __init__(self, *, poll_interval_seconds: float = 2.0) -> None:
        self._poll_interval_seconds = max(0.05, float(poll_interval_seconds))
        self._lock = threading.Lock()
        self._stop_event: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self._state = ScheduleStopWatcherState()
        self._generation = 0

    def available(self) -> bool:
        return True

    def state(self) -> ScheduleStopWatcherState:
        with self._lock:
            return self._state

    def arm(
        self,
        *,
        service: object,
        resolved: ResolvedPaths,
        proc: object,
        deadline: datetime,
    ) -> ScheduleStopWatcherState:
        self.cancel("replaced by a new schedule-stop watcher")
        pid = int(getattr(proc, "pid", 0) or 0)
        stop_event = threading.Event()
        with self._lock:
            self._generation += 1
            generation = self._generation
            state = ScheduleStopWatcherState(
                status="armed",
                pid=pid,
                deadline=deadline.isoformat(),
                stop_requested=False,
                generation=generation,
                message=f"Backend schedule-stop watcher armed for PID {pid} at {deadline.isoformat()}.",
            )
            self._stop_event = stop_event
            self._state = state
        thread = threading.Thread(
            target=self._run,
            name="MediaPipelineScheduleStopWatcher",
            daemon=True,
            args=(service, resolved, proc, deadline, stop_event, generation),
        )
        with self._lock:
            self._thread = thread
        thread.start()
        return state

    def cancel(self, reason: str = "schedule-stop watcher canceled") -> None:
        with self._lock:
            stop_event = self._stop_event
            thread = self._thread
            current = self._state
            self._generation += 1
            self._stop_event = None
            self._thread = None
            if current.status == "armed":
                self._state = ScheduleStopWatcherState(
                    status="canceled",
                    pid=current.pid,
                    deadline=current.deadline,
                    stop_requested=False,
                    generation=self._generation,
                    message=reason,
                )
        if stop_event is not None:
            stop_event.set()
        if thread is not None and thread.is_alive():
            thread.join(timeout=1.0)

    def _set_state(self, state: ScheduleStopWatcherState, *, generation: int) -> None:
        with self._lock:
            if generation != self._generation:
                return
            self._state = state
            if state.status != "armed":
                self._stop_event = None
                self._thread = None

    def _run(
        self,
        service: object,
        resolved: ResolvedPaths,
        proc: object,
        deadline: datetime,
        stop_event: threading.Event,
        generation: int,
    ) -> None:
        pid = int(getattr(proc, "pid", 0) or 0)
        while not stop_event.is_set():
            poll = getattr(proc, "poll", None)
            if callable(poll):
                try:
                    return_code = poll()
                except Exception as exc:
                    self._set_state(
                        ScheduleStopWatcherState(
                            status="error",
                            pid=pid,
                            deadline=deadline.isoformat(),
                            stop_requested=False,
                            generation=generation,
                            message="Backend schedule-stop watcher could not poll the process.",
                            error=str(exc),
                        ),
                        generation=generation,
                    )
                    return
                if return_code is not None:
                    self._set_state(
                        ScheduleStopWatcherState(
                            status="completed",
                            pid=pid,
                            deadline=deadline.isoformat(),
                            stop_requested=False,
                            generation=generation,
                            message=f"Pipeline PID {pid} exited before the schedule stop boundary.",
                        ),
                        generation=generation,
                    )
                    return
            if _now_for_deadline(deadline) >= deadline:
                writer = getattr(service, "write_flag", None)
                if not callable(writer):
                    self._set_state(
                        ScheduleStopWatcherState(
                            status="error",
                            pid=pid,
                            deadline=deadline.isoformat(),
                            stop_requested=False,
                            generation=generation,
                            message="Backend schedule-stop watcher could not request Stop because write_flag is unavailable.",
                            error="write_flag unavailable",
                        ),
                        generation=generation,
                    )
                    return
                try:
                    message = str(writer(resolved.stop_flag, "Stop"))
                except Exception as exc:
                    self._set_state(
                        ScheduleStopWatcherState(
                            status="error",
                            pid=pid,
                            deadline=deadline.isoformat(),
                            stop_requested=False,
                            generation=generation,
                            message=f"Backend schedule-stop watcher failed to request Stop for PID {pid}.",
                            error=str(exc),
                        ),
                        generation=generation,
                    )
                    return
                self._set_state(
                    ScheduleStopWatcherState(
                        status="stop_requested",
                        pid=pid,
                        deadline=deadline.isoformat(),
                        stop_requested=True,
                        generation=generation,
                        message=f"Schedule window ended. Stop requested for PID {pid}: {message}",
                    ),
                    generation=generation,
                )
                return
            remaining = max(0.05, min(self._poll_interval_seconds, (deadline - _now_for_deadline(deadline)).total_seconds()))
            stop_event.wait(remaining)


def schedule_stop_watcher_state_mapping(watcher: object) -> dict[str, Any]:
    state_reader = getattr(watcher, "state", None)
    if not callable(state_reader):
        return {
            "status": "unavailable",
            "pid": 0,
            "deadline": "",
            "stop_requested": False,
            "generation": 0,
            "message": "Backend schedule-stop watcher is not available.",
            "error": "",
        }
    try:
        state = state_reader()
        to_mapping = getattr(state, "to_mapping", None)
        raw_state = to_mapping() if callable(to_mapping) else state
        mapped = dict(raw_state) if isinstance(raw_state, dict) else {}
    except Exception as exc:
        return {
            "status": "error",
            "pid": 0,
            "deadline": "",
            "stop_requested": False,
            "generation": 0,
            "message": "Backend schedule-stop watcher state could not be read.",
            "error": str(exc),
        }
    defaults = {
        "status": "unknown",
        "pid": 0,
        "deadline": "",
        "stop_requested": False,
        "generation": 0,
        "message": "",
        "error": "",
    }
    defaults.update(mapped)
    return defaults
