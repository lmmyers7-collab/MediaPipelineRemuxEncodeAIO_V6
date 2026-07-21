from __future__ import annotations

import sys
import tempfile
import threading
import time
import unittest
from datetime import datetime, timedelta
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.application.schedule_stop_watcher import (  # noqa: E402
    ScheduleStopWatcherManager,
    parse_schedule_stop_deadline,
    schedule_stop_deadline_from_gate,
    schedule_stop_watcher_state_mapping,
)
from mediapipeline.desktop.api import LocalApiServer  # noqa: E402
from mediapipeline.desktop.application import MediaPipelineApplicationFacade  # noqa: E402
from mediapipeline.desktop.models import ResolvedPaths  # noqa: E402

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_local_api_lifecycle_contract_smoke import _json_request, _service_with_idle_fixture
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_local_api_lifecycle_contract_smoke import _json_request, _service_with_idle_fixture


class FakeProc:
    pid = 24680

    def __init__(
        self,
        return_code: int | None = None,
        poll_exception: Exception | None = None,
        launch_id: str = "schedule-launch-24680",
    ) -> None:
        self.return_code = return_code
        self.poll_exception = poll_exception
        self._mediapipeline_launch_id = launch_id

    def poll(self) -> int | None:
        if self.poll_exception is not None:
            raise self.poll_exception
        return self.return_code


class FakeService:
    def __init__(self) -> None:
        self.calls: list[tuple[Path | None, str, int | None, str]] = []

    def write_stop_after_current_flag(
        self,
        flag_path: Path | None,
        *,
        run_id: str = "",
        target_pid: int | None = None,
        target_launch_id: str = "",
    ) -> str:
        self.calls.append((flag_path, run_id, target_pid, target_launch_id))
        if flag_path is not None:
            flag_path.parent.mkdir(parents=True, exist_ok=True)
            flag_path.write_text("Stop After Current", encoding="utf-8")
        return "Stop After Current requested."


class BlockingBrokenProc:
    pid = 13579

    def __init__(self) -> None:
        self.release = threading.Event()

    def poll(self) -> int | None:
        self.release.wait(timeout=2.0)
        raise RuntimeError("stale watcher poll should not replace current state")


class BrokenWatcher:
    def state(self) -> object:
        raise RuntimeError("watcher locked")


class BrokenFlagService:
    def write_stop_after_current_flag(
        self,
        flag_path: Path | None,
        *,
        run_id: str = "",
        target_pid: int | None = None,
        target_launch_id: str = "",
    ) -> str:
        _ = flag_path, run_id, target_pid, target_launch_id
        raise RuntimeError("disk locked")


def _resolved(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=None,
        stop_flag=root / "State" / "Pipeline" / "pipeline_stop.flag",
        stop_after_current_flag=root / "State" / "Pipeline" / "pipeline_stop_after_current.flag",
    )


def _wait_for_status(manager: ScheduleStopWatcherManager, status: str, *, timeout_seconds: float = 1.5):
    deadline = time.monotonic() + timeout_seconds
    last_state = manager.state()
    while time.monotonic() < deadline:
        last_state = manager.state()
        if last_state.status == status:
            return last_state
        time.sleep(0.02)
    raise AssertionError(f"Timed out waiting for watcher status {status!r}; last state was {last_state!r}")


class ScheduleStopWatcherTests(unittest.TestCase):
    def test_deadline_parsing_accepts_datetime_and_iso_strings(self) -> None:
        deadline = datetime(2026, 5, 14, 22, 30)

        self.assertIs(parse_schedule_stop_deadline(deadline), deadline)
        self.assertEqual(parse_schedule_stop_deadline("2026-05-14T22:30:00"), deadline)
        self.assertIsNone(parse_schedule_stop_deadline(""))
        self.assertIsNone(parse_schedule_stop_deadline(None))
        self.assertIsNone(parse_schedule_stop_deadline("none"))
        self.assertIsNone(parse_schedule_stop_deadline("not-a-date"))
        self.assertEqual(
            schedule_stop_deadline_from_gate({"data": {"current_window_end": "2026-05-14T22:30:00"}}),
            deadline,
        )
        self.assertIsNone(schedule_stop_deadline_from_gate({}))
        self.assertIsNone(schedule_stop_deadline_from_gate({"data": "not-a-mapping"}))

    def test_watcher_requests_stop_when_deadline_arrives(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manager = ScheduleStopWatcherManager(poll_interval_seconds=0.05)
            service = FakeService()
            resolved = _resolved(root)

            manager.arm(
                service=service,
                resolved=resolved,
                proc=FakeProc(),
                deadline=datetime.now() - timedelta(seconds=1),
            )
            state = _wait_for_status(manager, "stop_requested")
            stop_flag_exists = bool(resolved.stop_after_current_flag and resolved.stop_after_current_flag.exists())

        self.assertEqual(state.status, "stop_requested")
        self.assertTrue(state.stop_requested)
        self.assertGreater(state.generation, 0)
        self.assertEqual(
            service.calls,
            [(resolved.stop_after_current_flag, "", FakeProc.pid, "schedule-launch-24680")],
        )
        self.assertTrue(stop_flag_exists)

    def test_watcher_rejects_deadline_request_without_exact_launch_identity(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manager = ScheduleStopWatcherManager(poll_interval_seconds=0.05)
            service = FakeService()
            resolved = _resolved(root)

            manager.arm(
                service=service,
                resolved=resolved,
                proc=FakeProc(launch_id=""),
                deadline=datetime.now() - timedelta(seconds=1),
            )
            state = _wait_for_status(manager, "error")

        self.assertIn("exact launch identity", state.message)
        self.assertEqual(service.calls, [])
        self.assertFalse(resolved.stop_after_current_flag.exists())

    def test_watcher_exits_without_stop_when_process_finishes_first(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manager = ScheduleStopWatcherManager(poll_interval_seconds=0.05)
            service = FakeService()
            resolved = _resolved(root)

            manager.arm(
                service=service,
                resolved=resolved,
                proc=FakeProc(return_code=0),
                deadline=datetime.now() + timedelta(seconds=10),
            )
            state = _wait_for_status(manager, "completed")

        self.assertEqual(state.status, "completed")
        self.assertFalse(state.stop_requested)
        self.assertGreater(state.generation, 0)
        self.assertEqual(service.calls, [])

    def test_cancel_stops_armed_watcher_without_writing_flag(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manager = ScheduleStopWatcherManager(poll_interval_seconds=0.05)
            service = FakeService()
            resolved = _resolved(root)

            manager.arm(
                service=service,
                resolved=resolved,
                proc=FakeProc(),
                deadline=datetime.now() + timedelta(seconds=10),
            )
            manager.cancel("test cancel")
            state = manager.state()

        self.assertEqual(state.status, "canceled")
        self.assertEqual(state.message, "test cancel")
        self.assertGreater(state.generation, 0)
        self.assertEqual(service.calls, [])

    def test_stale_watcher_thread_cannot_overwrite_rearmed_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manager = ScheduleStopWatcherManager(poll_interval_seconds=0.05)
            service = FakeService()
            resolved = _resolved(root)
            stale_proc = BlockingBrokenProc()

            manager.arm(
                service=service,
                resolved=resolved,
                proc=stale_proc,
                deadline=datetime.now() + timedelta(seconds=10),
            )
            manager.cancel("replace stale watcher")
            replacement_state = manager.arm(
                service=service,
                resolved=resolved,
                proc=FakeProc(),
                deadline=datetime.now() + timedelta(seconds=10),
            )
            replacement_generation = replacement_state.generation
            stale_proc.release.set()
            time.sleep(0.1)
            state = manager.state()
            manager.cancel("test cleanup")

        self.assertEqual(replacement_state.status, "armed")
        self.assertGreater(replacement_generation, 0)
        self.assertEqual(state.status, "armed")
        self.assertEqual(state.pid, FakeProc.pid)
        self.assertEqual(state.generation, replacement_generation)
        self.assertEqual(state.error, "")
        self.assertEqual(service.calls, [])

    def test_state_mapping_handles_missing_and_broken_watchers(self) -> None:
        self.assertEqual(schedule_stop_watcher_state_mapping(None)["status"], "unavailable")
        self.assertEqual(schedule_stop_watcher_state_mapping(None)["generation"], 0)
        broken = schedule_stop_watcher_state_mapping(BrokenWatcher())
        self.assertEqual(broken["status"], "error")
        self.assertEqual(broken["generation"], 0)
        self.assertIn("watcher locked", broken["error"])

    def test_watcher_reports_poll_exception_without_writing_stop_flag(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manager = ScheduleStopWatcherManager(poll_interval_seconds=0.05)
            service = FakeService()
            resolved = _resolved(root)

            manager.arm(
                service=service,
                resolved=resolved,
                proc=FakeProc(poll_exception=RuntimeError("process handle closed")),
                deadline=datetime.now() + timedelta(seconds=10),
            )
            state = _wait_for_status(manager, "error")

        self.assertIn("could not poll", state.message)
        self.assertIn("process handle closed", state.error)
        self.assertGreater(state.generation, 0)
        self.assertEqual(service.calls, [])

    def test_watcher_reports_missing_stop_after_current_writer_at_deadline(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manager = ScheduleStopWatcherManager(poll_interval_seconds=0.05)
            resolved = _resolved(root)

            manager.arm(
                service=object(),
                resolved=resolved,
                proc=FakeProc(),
                deadline=datetime.now() - timedelta(seconds=1),
            )
            state = _wait_for_status(manager, "error")

        self.assertEqual(state.error, "write_stop_after_current_flag unavailable")
        self.assertGreater(state.generation, 0)
        self.assertIn("write_stop_after_current_flag is unavailable", state.message)

    def test_watcher_reports_stop_after_current_failure_at_deadline(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            manager = ScheduleStopWatcherManager(poll_interval_seconds=0.05)
            resolved = _resolved(root)

            manager.arm(
                service=BrokenFlagService(),
                resolved=resolved,
                proc=FakeProc(),
                deadline=datetime.now() - timedelta(seconds=1),
            )
            state = _wait_for_status(manager, "error")

        self.assertIn("failed to request Stop After Current", state.message)
        self.assertIn("disk locked", state.error)
        self.assertGreater(state.generation, 0)

    def test_local_api_exposes_stop_requested_watcher_without_blocking_safe_close(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, service = _service_with_idle_fixture(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-watch-stop-requested")
            facade._schedule_stop_watcher.arm(  # type: ignore[attr-defined]
                service=service,
                resolved=resolved,
                proc=FakeProc(),
                deadline=datetime.now() - timedelta(seconds=1),
            )
            watcher_state = _wait_for_status(facade._schedule_stop_watcher, "stop_requested")  # type: ignore[attr-defined]
            server = LocalApiServer(
                facade,
                token="watcher-stop-requested-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                schedule_status, schedule_payload = _json_request(f"{server.url}/api/schedule", token=server.token)
                close_status, close_payload = _json_request(f"{server.url}/api/backend/close-readiness", token=server.token)
            finally:
                server.stop()

        self.assertTrue(watcher_state.stop_requested)
        self.assertGreater(watcher_state.generation, 0)
        self.assertEqual(schedule_status, 200)
        self.assertEqual(schedule_payload["schema_version"], "desktop_schedule_workspace.v1")
        schedule_watcher = schedule_payload["continuous_watcher"]
        self.assertEqual(schedule_watcher["status"], "stop_requested")
        self.assertTrue(schedule_watcher["stop_requested"])
        self.assertEqual(schedule_watcher["generation"], watcher_state.generation)
        self.assertIn("Schedule window ended", schedule_watcher["message"])
        self.assertEqual(close_status, 200)
        self.assertTrue(close_payload["safe_to_close"])
        self.assertFalse(close_payload["active_work"])
        self.assertEqual(close_payload["continuous_watcher"]["status"], "stop_requested")
        self.assertTrue(close_payload["continuous_watcher"]["stop_requested"])
        self.assertEqual(close_payload["continuous_watcher"]["generation"], watcher_state.generation)


if __name__ == "__main__":
    unittest.main()
