from __future__ import annotations

import io
import json
import logging
import sys
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.network.auth import validate_header
from mediapipeline.desktop.network.cluster_log import format_cluster_log_line
from mediapipeline.desktop.network.coordinator import (
    CoordinatorDispatcher,
    _CoordHandler,
    _coordinator_health_heartbeat_timeout_mins,
)
from mediapipeline.desktop.network.diagnostics import diagnostic_preview
from mediapipeline.desktop.network.firewall import (
    add_firewall_rule,
    build_add_firewall_rule_command,
    check_firewall_port,
    format_command,
    parse_matching_firewall_rule_names,
)
from mediapipeline.desktop.network.http_json import http_get_json, http_post_json
from mediapipeline.desktop.network.identity import (
    LOG_MESSAGE_TRUNCATION_SUFFIX,
    coerce_worker_name,
    is_valid_worker_id,
    sanitize_log_entry_fields,
)
from mediapipeline.desktop.network.coordinator_http import (
    MAX_COORDINATOR_BODY_BYTES,
    parse_query_params,
    validate_content_length,
)
from mediapipeline.desktop.network.coordinator_policy import (
    RETRY_AFTER_ACTIVE_SECONDS,
    RETRY_AFTER_IDLE_SECONDS,
    compute_retry_after_seconds,
    coordinator_bind_address,
    coordinator_port,
    heartbeat_timeout_mins,
)
from mediapipeline.desktop.network.coordinator_url import validate_coordinator_url
from mediapipeline.desktop.network.encode_config_snapshot import snapshot_encode_config
from mediapipeline.desktop.network.failure_policy import source_has_prior_failure
from mediapipeline.desktop.network.path_map import apply_source_path_map, parse_source_path_map
from mediapipeline.desktop.network.poll_policy import resolve_worker_poll_interval, resolve_worker_wait_seconds
from mediapipeline.desktop.network.probe import probe_coordinator_health, probe_worker_auth
from mediapipeline.desktop.network.protocol import ClaimResponse, DoneRequest, HeartbeatRequest, LogEntryRequest
from mediapipeline.desktop.network.registry import InFlightRegistry
from mediapipeline.desktop.network.share_block import (
    coerce_coordinator_port,
    format_coordinator_share_block,
    select_coordinator_share_ip,
)
from mediapipeline.desktop.network.threading_helpers import start_daemon_thread
from mediapipeline.desktop.network.worker_state import atomic_write_text, load_worker_state, save_worker_state
from mediapipeline.desktop.network.worker import (
    WorkerDispatcher,
    _atomic_write_text,
    _http_read_capped,
    _make_queue_record,
    _safe_hostname,
    _validate_coordinator_url,
)
from mediapipeline.desktop.network.worker_done import (
    build_completion_done_request,
    build_crash_recovery_done_request,
    build_release_done_request,
)
from mediapipeline.desktop.network.worker_record import make_queue_record


class NetworkWorkerRuntimeTests(unittest.TestCase):
    def test_firewall_add_rule_command_limits_profile_and_remote_scope(self) -> None:
        command = build_add_firewall_rule_command(7830, netsh_path="netsh")
        manual_command = format_command(command)

        self.assertIn("profile=private", command)
        self.assertIn("remoteip=localsubnet", command)
        self.assertIn("profile=private", manual_command)
        self.assertIn("remoteip=localsubnet", manual_command)

    def test_network_diagnostic_preview_bounds_text(self) -> None:
        long_error = "network failure " + ("x" * 500) + "tail-marker"

        self.assertEqual(diagnostic_preview("short"), "short")
        preview = diagnostic_preview(RuntimeError(long_error), limit=80)
        self.assertIn("...<truncated>", preview)
        self.assertNotIn("tail-marker", preview)

    def test_start_daemon_thread_logs_start_failure_and_runs_handler(self) -> None:
        class BadThread:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

            def start(self) -> None:
                raise RuntimeError("thread denied")

        failures: list[Exception] = []
        logger = logging.getLogger("mediapipeline.desktop.network.threading_helpers")

        with (
            patch("mediapipeline.desktop.network.threading_helpers.threading.Thread", BadThread),
            self.assertLogs("mediapipeline.desktop.network.threading_helpers", level="WARNING") as logs,
        ):
            thread = start_daemon_thread(
                name="network-test",
                target=lambda: self.fail("target should not run"),
                log=logger,
                failure_message="Network test thread failed to start",
                on_failure=failures.append,
            )

        self.assertIsNone(thread)
        self.assertEqual(len(failures), 1)
        self.assertEqual(str(failures[0]), "thread denied")
        self.assertIn("Network test thread failed to start: thread denied", "\n".join(logs.output))

    def test_worker_source_path_map_preserves_order_and_rewrites_prefixes(self) -> None:
        mappings = parse_source_path_map(
            json.dumps(
                {
                    r"\\SERVER/Media/Shows": r"D:/Shows",
                    r"\\SERVER/Media": r"E:/Media",
                }
            )
        )

        self.assertEqual(
            mappings,
            [(r"\\SERVER\Media\Shows", r"D:\Shows"), (r"\\SERVER\Media", r"E:\Media")],
        )
        self.assertEqual(
            apply_source_path_map(r"\\server\media\shows\Example\S01E01.mkv", mappings),
            r"D:\Shows\Example\S01E01.mkv",
        )
        self.assertEqual(
            apply_source_path_map(r"\\SERVER\MediaExtra\movie.mkv", mappings),
            r"\\SERVER\MediaExtra\movie.mkv",
        )

    def test_worker_source_path_map_logs_unparseable_entries(self) -> None:
        class BadString:
            def __str__(self) -> str:
                raise RuntimeError("string conversion failed")

            def __repr__(self) -> str:
                raise RuntimeError("repr conversion failed")

        payload = {
            BadString(): r"D:\Skipped",
            r"C:\Source": BadString(),
            r"D:\Source": r"E:\Mapped",
        }

        with (
            patch("mediapipeline.desktop.network.path_map.loads_strict_json", return_value=payload),
            self.assertLogs("mediapipeline.desktop.network.path_map", level="WARNING") as logs,
        ):
            mappings = parse_source_path_map("{}")

        self.assertEqual(mappings, [(r"D:\Source", r"E:\Mapped")])
        joined = "\n".join(logs.output)
        self.assertIn("WorkerSourcePathMap entry could not be parsed", joined)
        self.assertIn("<unrepresentable BadString", joined)

    def test_worker_dispatcher_source_path_map_methods_stay_compatible(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._source_path_map = WorkerDispatcher._parse_source_path_map(json.dumps({r"Z:\Media": r"D:\Media"}))

        self.assertEqual(worker._apply_path_map(r"z:\media\movie.mkv"), r"D:\Media\movie.mkv")

    def test_worker_status_callback_failure_is_logged(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)

        def bad_callback(_message: str) -> None:
            raise RuntimeError("callback failed")

        worker._status_callback = bad_callback

        with self.assertLogs("mediapipeline.desktop.network.worker", level="DEBUG") as logs:
            worker._notify_status("poll failed")

        self.assertIn("Worker status callback failed: callback failed", "\n".join(logs.output))

    def test_worker_status_callback_failure_diagnostic_is_bounded(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        long_error = "callback failed " + ("x" * 500) + "tail-marker"

        def bad_callback(_message: str) -> None:
            raise RuntimeError(long_error)

        worker._status_callback = bad_callback

        with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
            worker._notify_status("poll failed")

        output = "\n".join(logs.output)
        self.assertIn("Worker status callback failed", output)
        self.assertIn("...<truncated>", output)
        self.assertNotIn("tail-marker", output)

    def test_worker_cluster_log_thread_start_failure_is_logged(self) -> None:
        class BadThread:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

            def start(self) -> None:
                raise RuntimeError("thread denied")

        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._http_post = lambda *_args, **_kwargs: self.fail("cluster log post should not run")

        with (
            patch("mediapipeline.desktop.network.worker.threading.Thread", BadThread),
            self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs,
        ):
            worker.log_cluster_event(level="INFO", event="job_started", message="movie.mkv")

        self.assertIn(
            "Failed to start cluster log POST thread for event job_started: thread denied",
            "\n".join(logs.output),
        )

    def test_worker_local_cluster_log_mirror_redacts_token_assignment(self) -> None:
        class NoopThread:
            def __init__(self, *, target, **_kwargs) -> None:
                self._target = target

            def start(self) -> None:
                return None

        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._http_post = lambda *_args, **_kwargs: None

        with (
            patch("mediapipeline.desktop.network.worker.threading.Thread", NoopThread),
            self.assertLogs("mediapipeline.desktop.network.worker", level="INFO") as logs,
        ):
            worker.log_cluster_event(
                level="INFO",
                event="job_started",
                message="claim token=super-secret WorkerAuthToken=also-secret",
                job_id="job-token=job-secret",
            )

        output = "\n".join(logs.output)
        self.assertIn("token=<redacted>", output)
        self.assertIn("WorkerAuthToken=<redacted>", output)
        self.assertNotIn("super-secret", output)
        self.assertNotIn("also-secret", output)
        self.assertNotIn("job-secret", output)

    def test_worker_local_cluster_log_mirror_redacts_url_query_fragment_userinfo(self) -> None:
        class NoopThread:
            def __init__(self, *, target, **_kwargs) -> None:
                self._target = target

            def start(self) -> None:
                return None

        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._http_post = lambda *_args, **_kwargs: None

        with (
            patch("mediapipeline.desktop.network.worker.threading.Thread", NoopThread),
            self.assertLogs("mediapipeline.desktop.network.worker", level="INFO") as logs,
        ):
            worker.log_cluster_event(
                level="INFO",
                event="job_started",
                message="failed http://user:pass@coord.test:7830/api/log?token=url-secret#frag",
                source_path="http://user:pass@coord.test:7830/media/Movie.mkv?token=source-secret#frag",
            )

        output = "\n".join(logs.output)
        self.assertIn("http://coord.test:7830/api/log", output)
        self.assertNotIn("user:pass", output)
        self.assertNotIn("url-secret", output)
        self.assertNotIn("source-secret", output)
        self.assertNotIn("#frag", output)

    def test_worker_cluster_log_post_failure_warns_with_event_context(self) -> None:
        class InlineThread:
            def __init__(self, *, target, **_kwargs) -> None:
                self._target = target

            def start(self) -> None:
                self._target()

        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._http_post = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("coordinator offline"))

        with (
            patch("mediapipeline.desktop.network.worker.threading.Thread", InlineThread),
            self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs,
        ):
            worker.log_cluster_event(level="INFO", event="job_started", message="movie.mkv")

        self.assertIn(
            "cluster log POST failed for event job_started: coordinator offline",
            "\n".join(logs.output),
        )

    def test_worker_cluster_log_failure_diagnostics_are_bounded(self) -> None:
        long_error = "cluster offline " + ("x" * 500) + "tail-marker"

        class InlineThread:
            def __init__(self, *, target, **_kwargs) -> None:
                self._target = target

            def start(self) -> None:
                self._target()

        class BadThread:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

            def start(self) -> None:
                raise RuntimeError(long_error)

        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._http_post = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(long_error))

        with (
            patch("mediapipeline.desktop.network.worker.threading.Thread", InlineThread),
            self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs,
        ):
            worker.log_cluster_event(level="INFO", event="job_started", message="movie.mkv")
        post_output = "\n".join(logs.output)
        self.assertIn("...<truncated>", post_output)
        self.assertNotIn("tail-marker", post_output)

        with (
            patch("mediapipeline.desktop.network.worker.threading.Thread", BadThread),
            self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs,
        ):
            worker.log_cluster_event(level="INFO", event="job_started", message="movie.mkv")
        start_output = "\n".join(logs.output)
        self.assertIn("...<truncated>", start_output)
        self.assertNotIn("tail-marker", start_output)

        worker.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError(long_error))  # type: ignore[method-assign]
        with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
            WorkerDispatcher._safe_log_cluster_event(worker, "claim-record-invalid", job_id="job-1")
        safe_output = "\n".join(logs.output)
        self.assertIn("...<truncated>", safe_output)
        self.assertNotIn("tail-marker", safe_output)

    def test_worker_poll_thread_start_failure_raises_without_marking_started(self) -> None:
        class BadThread:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

            def start(self) -> None:
                raise RuntimeError("poll thread denied")

        with tempfile.TemporaryDirectory() as td:
            app = SimpleNamespace(
                _machine_id="worker-1",
                resolved=SimpleNamespace(
                    config_data={
                        "WorkerCoordinatorUrl": "http://127.0.0.1:7830",
                        "WorkerAuthToken": "token",
                        "WorkerName": "Worker",
                    }
                ),
                service=SimpleNamespace(app_state_path=Path(td) / "app_state.json"),
            )
            holder: dict[str, WorkerDispatcher] = {}
            original_crash_recover = WorkerDispatcher._crash_recover

            def capture_crash_recover(worker: WorkerDispatcher) -> None:
                holder["worker"] = worker
                original_crash_recover(worker)

            with (
                patch("mediapipeline.desktop.network.worker.threading.Thread", BadThread),
                patch.object(WorkerDispatcher, "_crash_recover", capture_crash_recover),
                self.assertLogs("mediapipeline.desktop.network.worker", level="ERROR") as logs,
            ):
                with self.assertRaisesRegex(RuntimeError, "Could not start worker poll thread"):
                    WorkerDispatcher(app)

            worker = holder["worker"]
            self.assertIsNone(worker._poll_thread)
            self.assertIn(
                "Could not start worker poll thread for coordinator http://127.0.0.1:7830: poll thread denied",
                "\n".join(logs.output),
            )

    def test_worker_heartbeat_post_failure_updates_operator_status(self) -> None:
        class OneShotStop:
            def __init__(self) -> None:
                self.calls = 0

            def wait(self, _seconds: float) -> bool:
                self.calls += 1
                return self.calls > 1

        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker.app = SimpleNamespace(snapshot=None)
        worker._worker_id = "worker-1"
        worker._heartbeat_stop = OneShotStop()
        worker._http_post = lambda _path, _data: (_ for _ in ()).throw(RuntimeError("coordinator offline"))
        statuses: list[str] = []
        worker._notify_status = statuses.append
        job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"))

        WorkerDispatcher._heartbeat_loop(worker, job)

        self.assertEqual(statuses, ["⚠ Heartbeat failed: coordinator offline"])

    def test_worker_heartbeat_failures_abort_before_lease_expiry(self) -> None:
        class TwoFailureStop:
            def wait(self, _seconds: float) -> bool:
                return False

        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker.app = SimpleNamespace(
            snapshot=None,
            resolved=SimpleNamespace(config_data={"CoordinatorHeartbeatTimeoutMins": 2}),
        )
        worker._worker_id = "worker-1"
        worker._heartbeat_stop = TwoFailureStop()
        worker._http_post = lambda _path, _data: (_ for _ in ()).throw(RuntimeError("coordinator offline"))
        worker._last_heartbeat_failure_text = ""
        worker._heartbeat_failure_started_monotonic = None
        worker._heartbeat_failure_started_at = ""
        worker._heartbeat_failure_age_seconds = 0
        worker._heartbeat_failure_abort_threshold_seconds_value = 0
        statuses: list[str] = []
        aborts: list[object] = []
        events: list[dict[str, object]] = []
        worker._notify_status = statuses.append
        worker._request_abort_reclaimed_job = aborts.append  # type: ignore[method-assign]
        worker._safe_log_cluster_event = lambda context, **kwargs: events.append({"context": context, **kwargs})  # type: ignore[method-assign]
        job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"))

        with patch("mediapipeline.desktop.network.worker_loops.time.monotonic", side_effect=[100.0, 161.0]):
            WorkerDispatcher._heartbeat_loop(worker, job)

        self.assertEqual(aborts, [job])
        self.assertEqual(worker._heartbeat_failure_age_seconds, 61)
        self.assertEqual(worker._heartbeat_failure_abort_threshold_seconds_value, 60)
        self.assertTrue(worker._job_reclaimed)
        self.assertIn("⚠ Heartbeat failed for 61s — aborting movie.mkv", statuses)
        self.assertEqual(events[-1]["event"], "heartbeat_failure_abort")

    def test_worker_stop_heartbeat_warns_when_thread_does_not_exit(self) -> None:
        class StuckHeartbeatThread:
            def __init__(self) -> None:
                self.join_timeout: float | None = None

            def is_alive(self) -> bool:
                return True

            def join(self, timeout: float | None = None) -> None:
                self.join_timeout = timeout

        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._heartbeat_stop = threading.Event()
        stuck_thread = StuckHeartbeatThread()
        worker._heartbeat_thread = stuck_thread

        with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
            WorkerDispatcher._stop_heartbeat(worker)

        self.assertTrue(worker._heartbeat_stop.is_set())
        self.assertEqual(stuck_thread.join_timeout, 5)
        self.assertIsNone(worker._heartbeat_thread)
        self.assertIn("Worker heartbeat thread did not stop within 5 seconds", "\n".join(logs.output))

    def test_worker_shutdown_warns_when_poll_thread_does_not_exit(self) -> None:
        class StuckPollThread:
            def __init__(self) -> None:
                self.join_timeout: float | None = None

            def is_alive(self) -> bool:
                return True

            def join(self, timeout: float | None = None) -> None:
                self.join_timeout = timeout

        heartbeat_stops: list[bool] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_name = "Worker"
        worker._poll_stop = threading.Event()
        worker._active_job_lock = threading.Lock()
        worker._active_job = None
        worker._stop_heartbeat = lambda: heartbeat_stops.append(True)  # type: ignore[method-assign]
        worker.log_cluster_event = lambda **_kwargs: None  # type: ignore[method-assign]
        stuck_thread = StuckPollThread()
        worker._poll_thread = stuck_thread

        with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
            WorkerDispatcher.shutdown(worker)

        self.assertTrue(worker._poll_stop.is_set())
        self.assertEqual(heartbeat_stops, [True])
        self.assertEqual(stuck_thread.join_timeout, 5)
        self.assertIn("Worker poll thread did not stop within 5 seconds", "\n".join(logs.output))

    def test_worker_shutdown_cluster_log_failure_still_releases_active_job(self) -> None:
        class StoppedPollThread:
            def is_alive(self) -> bool:
                return False

        released: list[object] = []
        job = object()
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_name = "Worker"
        worker._poll_stop = threading.Event()
        worker._active_job_lock = threading.Lock()
        worker._active_job = job
        worker._poll_thread = StoppedPollThread()
        worker.release = lambda active_job: released.append(active_job)  # type: ignore[method-assign]
        worker.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster unavailable"))  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
            WorkerDispatcher.shutdown(worker)

        self.assertTrue(worker._poll_stop.is_set())
        self.assertEqual(released, [job])
        self.assertIn("Failed to emit worker-stopped cluster event", "\n".join(logs.output))

    def test_worker_shutdown_preserve_active_job_keeps_claim_and_heartbeat(self) -> None:
        class StoppedPollThread:
            def is_alive(self) -> bool:
                return False

        released: list[object] = []
        heartbeat_stops: list[bool] = []
        job = SimpleNamespace(job_id="job-1")
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_name = "Worker"
        worker._poll_stop = threading.Event()
        worker._active_job_lock = threading.Lock()
        worker._active_job = job
        worker._poll_thread = StoppedPollThread()
        worker.release = lambda active_job: released.append(active_job)  # type: ignore[method-assign]
        worker._stop_heartbeat = lambda: heartbeat_stops.append(True)  # type: ignore[method-assign]
        worker.log_cluster_event = lambda **_kwargs: None  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
            WorkerDispatcher.shutdown(worker, release_active_job=False, preserve_active_job=True)

        self.assertTrue(worker._poll_stop.is_set())
        self.assertEqual(released, [])
        self.assertEqual(heartbeat_stops, [])
        self.assertIs(worker._active_job, job)
        self.assertIn("shutdown preserved active job job-1", "\n".join(logs.output))

    def test_worker_auth_poll_cluster_log_failure_keeps_poll_loop_alive(self) -> None:
        statuses: list[str] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._poll_interval = 30
        worker._poll_stop = threading.Event()
        worker._wakeup = threading.Event()
        worker._active_job_lock = threading.Lock()
        worker._active_job = None
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._base_url = "http://127.0.0.1:7830"
        worker._http_get = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("HTTP Error 401: Unauthorized"))  # type: ignore[method-assign]
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker._wait_interruptible = lambda _seconds=None: worker._poll_stop.set()  # type: ignore[method-assign]
        worker.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster unavailable"))  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
            WorkerDispatcher._poll_loop(worker)

        self.assertEqual(statuses, ["⚠ Auth error — token does not match coordinator"])
        self.assertTrue(worker._poll_stop.is_set())
        self.assertIn("Failed to emit claim-unauthorized cluster event", "\n".join(logs.output))

    def test_flush_pending_done_report_holds_claims_when_worker_state_is_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "worker_state.json"
            state_path.write_text("{not json", encoding="utf-8")
            statuses: list[str] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = state_path
            worker._worker_id = "worker-1"
            worker._notify_status = statuses.append  # type: ignore[method-assign]
            worker._http_post = lambda *_args, **_kwargs: self.fail("corrupt worker_state should not post done")  # type: ignore[method-assign]

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                flushed = WorkerDispatcher._flush_pending_done_report(worker)

        self.assertFalse(flushed)
        self.assertEqual(statuses, ["⚠ Worker state unreadable; holding new claims until worker_state.json is repaired or cleared."])
        self.assertIn("worker_state.json is unreadable; holding new claims", "\n".join(logs.output))

    def test_worker_poll_loop_does_not_claim_when_worker_state_is_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "worker_state.json"
            state_path.write_text("{not json", encoding="utf-8")
            statuses: list[str] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._poll_interval = 30
            worker._poll_stop = threading.Event()
            worker._wakeup = threading.Event()
            worker._active_job_lock = threading.Lock()
            worker._active_job = None
            worker._worker_id = "worker-1"
            worker._worker_name = "Worker"
            worker._base_url = "http://127.0.0.1:7830"
            worker._state_path = state_path
            worker._notify_status = statuses.append  # type: ignore[method-assign]
            worker._http_get = lambda *_args, **_kwargs: self.fail("corrupt worker_state should hold before claim")  # type: ignore[method-assign]
            worker._wait_interruptible = lambda _seconds=None: worker._poll_stop.set()  # type: ignore[method-assign]

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                WorkerDispatcher._poll_loop(worker)

        self.assertEqual(statuses, ["⚠ Worker state unreadable; holding new claims until worker_state.json is repaired or cleared."])
        self.assertIn("worker_state.json is unreadable; holding new claims", "\n".join(logs.output))

    def test_worker_poll_does_not_treat_error_body_401_text_as_auth_failure(self) -> None:
        statuses: list[str] = []
        events: list[dict[str, object]] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._poll_interval = 30
        worker._poll_stop = threading.Event()
        worker._wakeup = threading.Event()
        worker._active_job_lock = threading.Lock()
        worker._active_job = None
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._base_url = "http://127.0.0.1:7830"
        worker._last_claim_failure_text = ""
        worker._http_get = lambda *_args, **_kwargs: (_ for _ in ()).throw(  # type: ignore[method-assign]
            RuntimeError("HTTP 500 from http://127.0.0.1:7830/api/claim: upstream body mentions 401")
        )
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker._wait_interruptible = lambda _seconds=None: worker._poll_stop.set()  # type: ignore[method-assign]
        worker.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING"):
            WorkerDispatcher._poll_loop(worker)

        self.assertEqual(statuses, ["⚠ Poll error: HTTP 500 from http://127.0.0.1:7830/api/claim: upstream body mentions 401"])
        self.assertEqual(events, [])

    def test_worker_poll_loop_logs_repeated_claim_failure_once(self) -> None:
        class StopAfterTwoLoops:
            def __init__(self) -> None:
                self.calls = 0

            def is_set(self) -> bool:
                self.calls += 1
                return self.calls > 2

        statuses: list[str] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._poll_interval = 30
        worker._poll_stop = StopAfterTwoLoops()
        worker._wakeup = threading.Event()
        worker._active_job_lock = threading.Lock()
        worker._active_job = None
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._base_url = "http://127.0.0.1:7830"
        worker._last_claim_failure_text = ""
        worker._http_get = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("connection refused"))  # type: ignore[method-assign]
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker._wait_interruptible = lambda _seconds=None: None  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
            WorkerDispatcher._poll_loop(worker)

        warnings = [
            line for line in logs.output
            if "Worker claim request failed; poll loop will retry" in line
        ]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(statuses, [
            "⚠ Cannot reach coordinator (http://127.0.0.1:7830)",
            "⚠ Cannot reach coordinator (http://127.0.0.1:7830)",
        ])
        self.assertEqual(worker._last_claim_failure_text, "connection refused")

    def test_worker_claim_request_failure_diagnostics_are_bounded(self) -> None:
        class StopAfterTwoLoops:
            def __init__(self) -> None:
                self.calls = 0

            def is_set(self) -> bool:
                self.calls += 1
                return self.calls > 2

        long_error = "coordinator protocol error " + ("x" * 500) + "tail-marker"
        statuses: list[str] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._poll_interval = 30
        worker._poll_stop = StopAfterTwoLoops()
        worker._wakeup = threading.Event()
        worker._active_job_lock = threading.Lock()
        worker._active_job = None
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._base_url = "http://127.0.0.1:7830"
        worker._last_claim_failure_text = ""
        worker._http_get = lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(long_error))  # type: ignore[method-assign]
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker._wait_interruptible = lambda _seconds=None: None  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline.desktop.network.worker", level="DEBUG") as logs:
            WorkerDispatcher._poll_loop(worker)

        output = "\n".join(logs.output)
        self.assertIn("Worker claim request failed; poll loop will retry", output)
        self.assertIn("Claim request still failing", output)
        self.assertIn("...<truncated>", output)
        self.assertNotIn("tail-marker", output)
        self.assertEqual(len(statuses), 2)
        self.assertTrue(all(status.startswith("⚠ Poll error:") for status in statuses))
        self.assertTrue(all("tail-marker" not in status for status in statuses))
        self.assertEqual(worker._last_claim_failure_text, long_error)

    def test_worker_releases_claim_when_heartbeat_thread_start_fails(self) -> None:
        class BadHeartbeatThread:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

            def start(self) -> None:
                raise RuntimeError("thread denied")

            def is_alive(self) -> bool:
                return False

        saves: list[object] = []
        posts: list[tuple[str, dict]] = []
        clears: list[bool] = []
        statuses: list[str] = []
        events: list[dict] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._active_job_lock = threading.Lock()
        worker._active_job = object()
        worker._save_worker_state = lambda job: saves.append(job)  # type: ignore[method-assign]
        worker._http_post = lambda path, payload: posts.append((path, payload)) or {}  # type: ignore[method-assign]
        worker._clear_worker_state = lambda: clears.append(True)  # type: ignore[method-assign]
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[method-assign]
        job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"))

        with (
            patch("mediapipeline.desktop.network.worker.threading.Thread", BadHeartbeatThread),
            self.assertLogs("mediapipeline.desktop.network.worker", level="ERROR") as logs,
        ):
            WorkerDispatcher._on_job_claimed(worker, job)

        self.assertEqual(saves, [job])
        self.assertEqual(statuses, ["⚠ Could not start heartbeat for claimed job: thread denied"])
        self.assertEqual(events[0]["event"], "heartbeat_start_failed")
        self.assertEqual(posts[0][0], "/api/done")
        self.assertTrue(posts[0][1]["released"])
        self.assertEqual(clears, [True])
        self.assertIsNone(worker._active_job)
        self.assertIn("Failed to start worker heartbeat thread for job job-1", "\n".join(logs.output))

    def test_worker_heartbeat_start_failure_diagnostic_is_bounded(self) -> None:
        long_error = "thread denied " + ("x" * 500) + "tail-marker"

        class BadHeartbeatThread:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

            def start(self) -> None:
                raise RuntimeError(long_error)

            def is_alive(self) -> bool:
                return False

        posts: list[tuple[str, dict]] = []
        statuses: list[str] = []
        events: list[dict[str, object]] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._active_job_lock = threading.Lock()
        worker._active_job = object()
        worker._save_worker_state = lambda _job: None  # type: ignore[method-assign]
        worker._http_post = lambda path, payload: posts.append((path, payload)) or {}  # type: ignore[method-assign]
        worker._clear_worker_state = lambda: None  # type: ignore[method-assign]
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[method-assign]
        job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"))

        with (
            patch("mediapipeline.desktop.network.worker.threading.Thread", BadHeartbeatThread),
            self.assertLogs("mediapipeline.desktop.network.worker", level="ERROR") as logs,
        ):
            WorkerDispatcher._on_job_claimed(worker, job)

        output = "\n".join(logs.output)
        self.assertIn("...<truncated>", output)
        self.assertNotIn("tail-marker", output)
        self.assertIn("Could not start heartbeat for claimed job", statuses[0])
        self.assertNotIn("tail-marker", statuses[0])
        self.assertEqual(events[0]["event"], "heartbeat_start_failed")
        self.assertIn("...<truncated>", str(events[0]["message"]))
        self.assertNotIn("tail-marker", str(events[0]["message"]))
        self.assertEqual(posts[0][0], "/api/done")

    def test_worker_poll_loop_releases_claim_when_claim_handoff_fails(self) -> None:
        class StopAfterOneLoop:
            def __init__(self) -> None:
                self.calls = 0

            def is_set(self) -> bool:
                self.calls += 1
                return self.calls > 1

        releases: list[str] = []
        statuses: list[str] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._poll_interval = 1.0
        worker._poll_stop = StopAfterOneLoop()
        worker._active_job_lock = threading.Lock()
        worker._active_job = None
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._http_get = lambda _path, _params: {  # type: ignore[method-assign]
            "status": "ok",
            "job_id": "job-1",
            "source_path": r"C:\Media\movie.mkv",
            "estimated_size_gb": 1.0,
        }
        worker._apply_path_map = lambda path: path  # type: ignore[method-assign]
        worker._on_job_claimed = lambda _job: (_ for _ in ()).throw(RuntimeError("handoff failed"))  # type: ignore[method-assign]
        worker._do_release = lambda job: releases.append(job.job_id) or setattr(worker, "_active_job", None)  # type: ignore[method-assign]
        worker._notify_status = statuses.append  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline.desktop.network.worker", level="ERROR") as logs:
            WorkerDispatcher._poll_loop(worker)

        self.assertEqual(releases, ["job-1"])
        self.assertEqual(statuses, ["⚠ Claimed job handoff failed: handoff failed"])
        self.assertIsNone(worker._active_job)
        self.assertIn("Worker failed after claiming job job-1; releasing claim.", "\n".join(logs.output))

    def test_worker_claim_request_reports_accessible_library_ids(self) -> None:
        class StopAfterOneLoop:
            def __init__(self) -> None:
                self.calls = 0

            def is_set(self) -> bool:
                self.calls += 1
                return self.calls > 1

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            movies = root / "Movies"
            tv = root / "TV"
            movies.mkdir()
            params_seen: list[dict[str, str]] = []
            statuses: list[str] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker.app = SimpleNamespace(
                resolved=SimpleNamespace(
                    config_data={
                        "SourceMovies": str(movies),
                        "SourceTV": str(tv),
                        "Outsource": str(root / "Out"),
                    }
                )
            )
            worker._poll_interval = 1.0
            worker._poll_stop = StopAfterOneLoop()
            worker._wakeup = SimpleNamespace(wait=lambda _seconds: False, clear=lambda: None)
            worker._active_job_lock = threading.Lock()
            worker._active_job = None
            worker._worker_id = "worker-1"
            worker._worker_name = "Worker"
            worker._flush_pending_done_report = lambda: True  # type: ignore[method-assign]
            worker._maybe_refresh_library_auto_map = lambda: None  # type: ignore[method-assign]
            worker._http_get = lambda _path, params: params_seen.append(dict(params)) or ClaimResponse.empty().to_dict()  # type: ignore[method-assign]
            worker._notify_status = statuses.append  # type: ignore[method-assign]

            WorkerDispatcher._poll_loop(worker)

        self.assertEqual(params_seen[0]["worker_id"], "worker-1")
        self.assertEqual(params_seen[0]["accessible_library_ids"], "movies")
        self.assertEqual(len(statuses), 1)

    def test_worker_heartbeat_reports_accessible_library_ids(self) -> None:
        class StopAfterOneHeartbeat:
            def __init__(self) -> None:
                self.calls = 0

            def wait(self, _seconds: float) -> bool:
                self.calls += 1
                return self.calls > 1

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            movies = root / "Movies"
            movies.mkdir()
            posts: list[tuple[str, dict[str, object]]] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker.app = SimpleNamespace(
                resolved=SimpleNamespace(
                    config_data={
                        "SourceMovies": str(movies),
                        "SourceTV": str(root / "TV"),
                        "Outsource": str(root / "Out"),
                    }
                ),
                snapshot=None,
            )
            worker._worker_id = "worker-1"
            worker._heartbeat_stop = StopAfterOneHeartbeat()
            worker._http_post = lambda path, payload: posts.append((path, payload)) or {"status": "ok"}  # type: ignore[method-assign]
            worker._last_heartbeat_failure_text = ""
            worker._notify_status = lambda _message: None  # type: ignore[method-assign]
            job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=str(movies / "movie.mkv")))

            WorkerDispatcher._heartbeat_loop(worker, job)

        self.assertEqual(posts[0][0], "/api/heartbeat")
        self.assertEqual(posts[0][1]["accessible_library_ids"], ["movies"])

    def test_worker_claim_handoff_failure_diagnostic_is_bounded(self) -> None:
        class StopAfterOneLoop:
            def __init__(self) -> None:
                self.calls = 0

            def is_set(self) -> bool:
                self.calls += 1
                return self.calls > 1

        long_error = "handoff failed " + ("x" * 500) + "tail-marker"
        releases: list[str] = []
        statuses: list[str] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._poll_interval = 1.0
        worker._poll_stop = StopAfterOneLoop()
        worker._active_job_lock = threading.Lock()
        worker._active_job = None
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._http_get = lambda _path, _params: {  # type: ignore[method-assign]
            "status": "ok",
            "job_id": "job-1",
            "source_path": r"C:\Media\movie.mkv",
            "estimated_size_gb": 1.0,
        }
        worker._apply_path_map = lambda path: path  # type: ignore[method-assign]
        worker._on_job_claimed = lambda _job: (_ for _ in ()).throw(RuntimeError(long_error))  # type: ignore[method-assign]
        worker._do_release = lambda job: releases.append(job.job_id) or setattr(worker, "_active_job", None)  # type: ignore[method-assign]
        worker._notify_status = statuses.append  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline.desktop.network.worker", level="ERROR") as logs:
            WorkerDispatcher._poll_loop(worker)

        output = "\n".join(logs.output)
        self.assertEqual(releases, ["job-1"])
        self.assertIn("Worker failed after claiming job job-1; releasing claim.", output)
        self.assertIn("...<truncated>", output)
        self.assertNotIn("tail-marker", output)
        self.assertIn("Claimed job handoff failed", statuses[0])
        self.assertNotIn("tail-marker", statuses[0])
        self.assertIsNone(worker._active_job)

    def test_worker_claimed_job_schedule_failure_diagnostic_is_bounded(self) -> None:
        class StartedHeartbeatThread:
            def __init__(self, *_args, **_kwargs) -> None:
                return None

            def start(self) -> None:
                return None

            def is_alive(self) -> bool:
                return False

        long_error = "ui schedule failed " + ("x" * 500) + "tail-marker"
        posts: list[tuple[str, dict]] = []
        statuses: list[str] = []
        events: list[dict[str, object]] = []
        cleanup: list[tuple[str, str]] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker.app = SimpleNamespace(_worker_start_single_file=lambda _job: None)
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._active_job_lock = threading.Lock()
        worker._active_job = object()
        worker._save_worker_state = lambda _job: None  # type: ignore[method-assign]
        worker._http_post = lambda path, payload: posts.append((path, payload)) or {}  # type: ignore[method-assign]
        worker._clear_worker_state_after_accepted_report = lambda job_id, context: cleanup.append((job_id, context))  # type: ignore[method-assign]
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[method-assign]

        def bad_post(_name: str, _callback: object) -> None:
            raise RuntimeError(long_error)

        worker._post_app_callback = bad_post  # type: ignore[method-assign]
        job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"))

        with (
            patch("mediapipeline.desktop.network.worker.threading.Thread", StartedHeartbeatThread),
            self.assertLogs("mediapipeline.desktop.network.worker", level="ERROR") as logs,
        ):
            WorkerDispatcher._on_job_claimed(worker, job)

        output = "\n".join(logs.output)
        self.assertIn("Failed to schedule _worker_start_single_file", output)
        self.assertIn("...<truncated>", output)
        self.assertNotIn("tail-marker", output)
        self.assertIn("Could not schedule claimed job", statuses[0])
        self.assertNotIn("tail-marker", statuses[0])
        self.assertEqual(events[0]["event"], "claim_received")
        self.assertEqual(posts[0][0], "/api/done")
        self.assertTrue(posts[0][1]["released"])
        self.assertEqual(cleanup, [("job-1", "internal release")])
        self.assertIsNone(worker._active_job)

    def test_worker_poll_loop_releases_malformed_claim_response(self) -> None:
        class StopAfterOneLoop:
            def __init__(self) -> None:
                self.calls = 0

            def is_set(self) -> bool:
                self.calls += 1
                return self.calls > 1

        posts: list[tuple[str, dict]] = []
        statuses: list[str] = []
        events: list[dict] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._poll_interval = 1.0
        worker._poll_stop = StopAfterOneLoop()
        worker._active_job_lock = threading.Lock()
        worker._active_job = None
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._http_get = lambda _path, _params: {  # type: ignore[method-assign]
            "status": "ok",
            "job_id": "job-1",
            "source_path": r"C:\Media\movie.mkv",
            "encode_config": "not-a-dict",
        }
        worker._http_post = lambda path, payload: posts.append((path, payload)) or {}  # type: ignore[method-assign]
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[method-assign]
        worker._wait_interruptible = lambda *_args, **_kwargs: None  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
            WorkerDispatcher._poll_loop(worker)

        self.assertEqual(posts[0][0], "/api/done")
        self.assertEqual(posts[0][1]["job_id"], "job-1")
        self.assertTrue(posts[0][1]["released"])
        self.assertEqual(events[0]["event"], "claim_response_invalid")
        self.assertEqual(len(statuses), 1)
        self.assertIn("Released unstartable claim: malformed claim response", statuses[0])
        self.assertIsNone(worker._active_job)
        self.assertIn("Malformed claimed response for job job-1; releasing claim", "\n".join(logs.output))

    def test_worker_release_malformed_claim_response_survives_cluster_log_failure(self) -> None:
        posts: list[tuple[str, dict]] = []
        statuses: list[str] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_id = "worker-1"
        worker._http_post = lambda path, payload: posts.append((path, payload)) or {}  # type: ignore[method-assign]
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster log blocked"))  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
            released = WorkerDispatcher._release_malformed_claim_response(
                worker,
                {"status": "ok", "job_id": "job-1", "source_path": r"C:\Media\movie.mkv"},
                "bad encode_config",
            )

        self.assertTrue(released)
        self.assertEqual(posts[0][0], "/api/done")
        self.assertEqual(posts[0][1]["job_id"], "job-1")
        self.assertTrue(posts[0][1]["released"])
        self.assertEqual(len(statuses), 1)
        self.assertIn("malformed claim response", statuses[0])
        self.assertIn("Failed to emit malformed-claim cluster event for job job-1", "\n".join(logs.output))

    def test_worker_release_malformed_claim_response_bounds_reason_text(self) -> None:
        posts: list[tuple[str, dict]] = []
        statuses: list[str] = []
        events: list[dict[str, object]] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_id = "worker-1"
        worker._http_post = lambda path, payload: posts.append((path, payload)) or {}  # type: ignore[method-assign]
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[method-assign]
        reason = "bad retry_after_seconds: " + ("x" * 500) + "tail-marker"

        with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
            released = WorkerDispatcher._release_malformed_claim_response(
                worker,
                {"status": "ok", "job_id": "job-1", "source_path": r"C:\Media\movie.mkv"},
                reason,
            )

        self.assertTrue(released)
        self.assertEqual(posts[0][0], "/api/done")
        self.assertEqual(events[0]["event"], "claim_response_invalid")
        self.assertIn("...<truncated>", str(events[0]["message"]))
        self.assertIn("malformed claim response", statuses[0])
        self.assertNotIn("tail-marker", str(events[0]["message"]))
        self.assertNotIn("tail-marker", statuses[0])
        self.assertNotIn("tail-marker", "\n".join(logs.output))

    def test_worker_malformed_claim_release_post_failure_saves_pending_release(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "worker_state.json"
            statuses: list[str] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = state_path
            worker._worker_id = "worker-1"
            worker._http_post = lambda _path, _payload: (_ for _ in ()).throw(RuntimeError("coordinator offline"))  # type: ignore[method-assign]
            worker._notify_status = statuses.append  # type: ignore[method-assign]
            worker.log_cluster_event = lambda **_kwargs: None  # type: ignore[method-assign]

            released = WorkerDispatcher._release_malformed_claim_response(
                worker,
                {"status": "ok", "job_id": "job-1", "source_path": r"C:\Media\movie.mkv"},
                "bad encode_config",
            )

            state = load_worker_state(state_path)

        self.assertTrue(released)
        self.assertEqual(statuses, ["⚠ Release report queued for retry: coordinator offline"])
        self.assertEqual(state["job_id"], "job-1")
        self.assertTrue(state["pending_done_report"]["released"])

    def test_worker_poll_loop_rejects_ok_claim_missing_source_without_release_or_launch(self) -> None:
        class StopAfterOneLoop:
            def __init__(self) -> None:
                self.calls = 0

            def is_set(self) -> bool:
                self.calls += 1
                return self.calls > 1

        posts: list[tuple[str, dict]] = []
        statuses: list[str] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._poll_interval = 1.0
        worker._poll_stop = StopAfterOneLoop()
        worker._active_job_lock = threading.Lock()
        worker._active_job = None
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._base_url = "http://coordinator.test:7830"
        worker._http_get = lambda _path, _params: {"status": "ok", "job_id": "job-1"}  # type: ignore[method-assign]
        worker._http_post = lambda path, payload: posts.append((path, payload)) or {}  # type: ignore[method-assign]
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker._wait_interruptible = lambda *_args, **_kwargs: None  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
            WorkerDispatcher._poll_loop(worker)

        self.assertEqual(posts, [])
        self.assertIsNone(worker._active_job)
        self.assertIn("ok claim response requires non-empty job_id and source_path", "\n".join(logs.output))
        self.assertIn("Worker claim request failed", "\n".join(logs.output))
        self.assertEqual(len(statuses), 1)

    def test_worker_poll_loop_releases_claim_when_path_map_fails(self) -> None:
        class StopAfterOneLoop:
            def __init__(self) -> None:
                self.calls = 0

            def is_set(self) -> bool:
                self.calls += 1
                return self.calls > 1

        posts: list[tuple[str, dict]] = []
        statuses: list[str] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._poll_interval = 1.0
        worker._poll_stop = StopAfterOneLoop()
        worker._active_job_lock = threading.Lock()
        worker._active_job = None
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._http_get = lambda _path, _params: {  # type: ignore[method-assign]
            "status": "ok",
            "job_id": "job-1",
            "source_path": r"C:\Media\movie.mkv",
            "estimated_size_gb": 1.0,
        }
        worker._http_post = lambda path, payload: posts.append((path, payload)) or {}  # type: ignore[method-assign]
        worker._apply_path_map = lambda _path: (_ for _ in ()).throw(RuntimeError("bad path map"))  # type: ignore[method-assign]
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster log blocked"))  # type: ignore[method-assign]
        worker._wait_interruptible = lambda *_args, **_kwargs: None  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
            WorkerDispatcher._poll_loop(worker)

        self.assertEqual(posts[0][0], "/api/done")
        self.assertEqual(posts[0][1]["job_id"], "job-1")
        self.assertTrue(posts[0][1]["released"])
        self.assertEqual(statuses, ["⚠ Released unstartable claim: path map failed: bad path map"])
        self.assertIsNone(worker._active_job)
        joined = "\n".join(logs.output)
        self.assertIn("Source path map failed for claimed job job-1: bad path map", joined)
        self.assertIn("Failed to emit path-map-failure cluster event for job job-1", joined)

    def test_worker_poll_loop_releases_hostile_mapped_claim_without_starting_work(self) -> None:
        class StopAfterOneLoop:
            def __init__(self) -> None:
                self.calls = 0

            def is_set(self) -> bool:
                self.calls += 1
                return self.calls > 1

        posts: list[tuple[str, dict]] = []
        statuses: list[str] = []
        started: list[object] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker.app = SimpleNamespace(_worker_start_single_file=started.append)
        worker._poll_interval = 1.0
        worker._poll_stop = StopAfterOneLoop()
        worker._active_job_lock = threading.Lock()
        worker._active_job = None
        worker._base_url = "http://coordinator.test:7830"
        worker._auth_token = "worker-token"
        worker._worker_id = "worker-1"
        worker._worker_name = "Worker"
        worker._source_path_map = parse_source_path_map(json.dumps({r"C:\Media": r"D:\WorkerMedia"}))
        worker._accessible_library_ids = lambda: []  # type: ignore[method-assign]
        worker._flush_pending_done_report = lambda: True  # type: ignore[method-assign]
        worker._maybe_refresh_library_auto_map = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        worker._http_get = lambda _path, _params: {  # type: ignore[method-assign]
            "status": "ok",
            "job_id": "job-1",
            "source_path": r"C:\Media\..\Secret\movie.mkv",
            "estimated_size_gb": 1.0,
        }
        worker._http_post = lambda path, payload: posts.append((path, payload)) or {}  # type: ignore[method-assign]
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker.log_cluster_event = lambda **_kwargs: None  # type: ignore[method-assign]
        worker._wait_interruptible = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
        worker._save_worker_state = lambda _job: self.fail("unsafe mapped claim reached worker_state save")  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline.desktop.network.worker", level="ERROR") as logs:
            WorkerDispatcher._poll_loop(worker)

        self.assertEqual(started, [])
        self.assertEqual(posts[0][0], "/api/done")
        self.assertEqual(posts[0][1]["job_id"], "job-1")
        self.assertTrue(posts[0][1]["released"])
        self.assertEqual(
            statuses,
            ["⚠ Released unstartable claim: path map failed: WorkerSourcePathMap mapped tail contains parent traversal."],
        )
        self.assertIn("Source path map failed for claimed job job-1", "\n".join(logs.output))

    def test_worker_path_map_release_post_failure_saves_pending_release(self) -> None:
        class StopAfterOneLoop:
            def __init__(self) -> None:
                self.calls = 0

            def is_set(self) -> bool:
                self.calls += 1
                return self.calls > 1

        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "worker_state.json"
            statuses: list[str] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = state_path
            worker._poll_interval = 1.0
            worker._poll_stop = StopAfterOneLoop()
            worker._active_job_lock = threading.Lock()
            worker._active_job = None
            worker._worker_id = "worker-1"
            worker._worker_name = "Worker"
            worker._http_get = lambda _path, _params=None: {  # type: ignore[method-assign]
                "status": "ok",
                "job_id": "job-1",
                "source_path": r"C:\Media\movie.mkv",
                "estimated_size_gb": 1.0,
            }
            worker._http_post = lambda _path, _payload: (_ for _ in ()).throw(RuntimeError("coordinator offline"))  # type: ignore[method-assign]
            worker._apply_path_map = lambda _path: (_ for _ in ()).throw(RuntimeError("bad path map"))  # type: ignore[method-assign]
            worker._notify_status = statuses.append  # type: ignore[method-assign]
            worker.log_cluster_event = lambda **_kwargs: None  # type: ignore[method-assign]
            worker._wait_interruptible = lambda *_args, **_kwargs: None  # type: ignore[method-assign]

            WorkerDispatcher._poll_loop(worker)

            state = load_worker_state(state_path)

        self.assertEqual(statuses, ["⚠ Release report queued for retry: coordinator offline"])
        self.assertEqual(state["job_id"], "job-1")
        self.assertTrue(state["pending_done_report"]["released"])

    def test_worker_heartbeat_sanitizes_snapshot_progress_before_post(self) -> None:
        class OneShotStop:
            def __init__(self) -> None:
                self.calls = 0

            def wait(self, _seconds: float) -> bool:
                self.calls += 1
                return self.calls > 1

        for raw_progress, expected in (("NaN", 0.0), (125, 100.0), (-5, 0.0)):
            with self.subTest(raw_progress=raw_progress):
                posts: list[dict[str, object]] = []
                worker = WorkerDispatcher.__new__(WorkerDispatcher)
                worker.app = SimpleNamespace(
                    snapshot=SimpleNamespace(
                        progress={"CurrentStagePercent": raw_progress, "CurrentStage": "encoding"}
                    )
                )
                worker._worker_id = "worker-1"
                worker._heartbeat_stop = OneShotStop()
                worker._http_post = lambda _path, data, posts=posts: posts.append(data) or {}
                worker._notify_status = lambda _message: None
                worker._job_reclaimed = False
                job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"))

                WorkerDispatcher._heartbeat_loop(worker, job)

                self.assertEqual(posts[0]["progress_percent"], expected)
                self.assertEqual(posts[0]["current_stage"], "encoding")

    def test_worker_heartbeat_snapshot_failure_logs_and_sends_safe_progress(self) -> None:
        class OneShotStop:
            def __init__(self) -> None:
                self.calls = 0

            def wait(self, _seconds: float) -> bool:
                self.calls += 1
                return self.calls > 1

        class BrokenSnapshot:
            @property
            def progress(self) -> dict[str, object]:
                raise RuntimeError("snapshot unavailable")

        posts: list[dict[str, object]] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker.app = SimpleNamespace(snapshot=BrokenSnapshot())
        worker._worker_id = "worker-1"
        worker._heartbeat_stop = OneShotStop()
        worker._http_post = lambda _path, data: posts.append(data) or {}
        worker._notify_status = lambda _message: None
        worker._job_reclaimed = False
        job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"))

        with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
            WorkerDispatcher._heartbeat_loop(worker, job)

        self.assertEqual(posts[0]["progress_percent"], 0.0)
        self.assertEqual(posts[0]["current_stage"], "")
        text = "\n".join(logs.output)
        self.assertIn("Heartbeat progress snapshot read failed for job job-1", text)
        self.assertIn("snapshot unavailable", text)

    def test_worker_heartbeat_post_failure_logs_repeated_error_once(self) -> None:
        class StopAfterTwoLoops:
            def __init__(self) -> None:
                self.calls = 0

            def wait(self, _seconds: float) -> bool:
                self.calls += 1
                return self.calls > 2

        statuses: list[str] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker.app = SimpleNamespace(snapshot=SimpleNamespace(progress={}))
        worker._worker_id = "worker-1"
        worker._heartbeat_stop = StopAfterTwoLoops()
        worker._http_post = lambda _path, _data: (_ for _ in ()).throw(RuntimeError("coordinator offline"))  # type: ignore[method-assign]
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker._job_reclaimed = False
        worker._last_heartbeat_failure_text = ""
        job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"))

        with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
            WorkerDispatcher._heartbeat_loop(worker, job)

        warnings = [
            line for line in logs.output
            if "Worker heartbeat POST failed for job job-1; heartbeat loop will retry" in line
        ]
        self.assertEqual(len(warnings), 1)
        self.assertEqual(statuses, ["⚠ Heartbeat failed: coordinator offline", "⚠ Heartbeat failed: coordinator offline"])
        self.assertEqual(worker._last_heartbeat_failure_text, "coordinator offline")

    def test_worker_heartbeat_post_failure_diagnostics_are_bounded(self) -> None:
        class StopAfterTwoLoops:
            def __init__(self) -> None:
                self.calls = 0

            def wait(self, _seconds: float) -> bool:
                self.calls += 1
                return self.calls > 2

        long_error = "coordinator offline " + ("x" * 500) + "tail-marker"
        statuses: list[str] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker.app = SimpleNamespace(snapshot=SimpleNamespace(progress={}))
        worker._worker_id = "worker-1"
        worker._heartbeat_stop = StopAfterTwoLoops()
        worker._http_post = lambda _path, _data: (_ for _ in ()).throw(RuntimeError(long_error))  # type: ignore[method-assign]
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker._job_reclaimed = False
        worker._last_heartbeat_failure_text = ""
        job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"))

        with self.assertLogs("mediapipeline.desktop.network.worker", level="DEBUG") as logs:
            WorkerDispatcher._heartbeat_loop(worker, job)

        output = "\n".join(logs.output)
        self.assertIn("Worker heartbeat POST failed for job job-1", output)
        self.assertIn("Heartbeat POST still failing for job job-1", output)
        self.assertIn("...<truncated>", output)
        self.assertNotIn("tail-marker", output)
        self.assertEqual(len(statuses), 2)
        self.assertTrue(all(status.startswith("⚠ Heartbeat failed:") for status in statuses))
        self.assertTrue(all("tail-marker" not in status for status in statuses))
        self.assertEqual(worker._last_heartbeat_failure_text, long_error)


class WorkerEncodeStartTests(unittest.TestCase):
    def test_on_job_claimed_callback_reaches_app_encode_entry_point(self) -> None:
        """Regression: the scheduled claim callback must invoke the app's
        encode entry point when executed (a stale attribute path here once
        passed the suite because the callback was never evaluated)."""

        class InertThread:
            def __init__(self, *args, **kwargs) -> None:
                return None

            def start(self) -> None:
                return None

            def is_alive(self) -> bool:
                return False

        started: list[object] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker.app = SimpleNamespace(_worker_start_single_file=started.append)
        worker._worker_id = "worker-1"
        worker._save_worker_state = lambda _job: None  # type: ignore[method-assign]
        worker._notify_status = lambda _msg: None  # type: ignore[method-assign]
        worker._safe_log_cluster_event = lambda context, **kwargs: None  # type: ignore[method-assign]
        worker._post_app_callback = lambda _name, callback: callback()  # type: ignore[method-assign]
        job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"))

        with patch("mediapipeline.desktop.network.worker_claims.threading.Thread", InertThread):
            WorkerDispatcher._on_job_claimed(worker, job)

        self.assertEqual(started, [job])

    def test_start_claimed_encode_failure_releases_claim(self) -> None:
        def boom(_job: object) -> None:
            raise RuntimeError("encode entry exploded")

        statuses: list[str] = []
        events: list[dict] = []
        releases: list[object] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker.app = SimpleNamespace(_worker_start_single_file=boom)
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker._safe_log_cluster_event = lambda context, **kwargs: events.append({"context": context, **kwargs})  # type: ignore[method-assign]
        worker._do_release = releases.append  # type: ignore[method-assign]
        job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"))

        with self.assertLogs("mediapipeline.desktop.network.worker", level="ERROR") as logs:
            WorkerDispatcher._start_claimed_encode(worker, job)

        self.assertEqual(releases, [job])
        self.assertEqual(events[0]["event"], "encode_start_failed")
        self.assertIn("Claimed job failed to start", statuses[0])
        self.assertIn("Worker encode start failed for job job-1", "\n".join(logs.output))


if __name__ == "__main__":
    unittest.main()
