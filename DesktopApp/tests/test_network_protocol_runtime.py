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
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.network.auth import validate_header
from mediapipeline_desktop_app.network.cluster_log import format_cluster_log_line
from mediapipeline_desktop_app.network.coordinator import (
    CoordinatorDispatcher,
    _CoordHandler,
    _coordinator_health_heartbeat_timeout_mins,
)
from mediapipeline_desktop_app.network.diagnostics import diagnostic_preview
from mediapipeline_desktop_app.network.firewall import (
    add_firewall_rule,
    build_add_firewall_rule_command,
    check_firewall_port,
    parse_matching_firewall_rule_names,
)
from mediapipeline_desktop_app.network.http_json import http_get_json, http_post_json
from mediapipeline_desktop_app.network.identity import (
    LOG_MESSAGE_TRUNCATION_SUFFIX,
    coerce_worker_name,
    is_valid_worker_id,
    sanitize_log_entry_fields,
)
from mediapipeline_desktop_app.network.coordinator_http import (
    MAX_COORDINATOR_BODY_BYTES,
    parse_query_params,
    validate_content_length,
)
from mediapipeline_desktop_app.network.coordinator_policy import (
    RETRY_AFTER_ACTIVE_SECONDS,
    RETRY_AFTER_IDLE_SECONDS,
    compute_retry_after_seconds,
    coordinator_bind_address,
    coordinator_port,
    heartbeat_timeout_mins,
)
from mediapipeline_desktop_app.network.coordinator_url import validate_coordinator_url
from mediapipeline_desktop_app.network.encode_config_snapshot import snapshot_encode_config
from mediapipeline_desktop_app.network.failure_policy import source_has_prior_failure
from mediapipeline_desktop_app.network.path_map import apply_source_path_map, parse_source_path_map
from mediapipeline_desktop_app.network.poll_policy import resolve_worker_poll_interval, resolve_worker_wait_seconds
from mediapipeline_desktop_app.network.probe import probe_coordinator_health, probe_worker_auth
from mediapipeline_desktop_app.network.protocol import ClaimResponse, DoneRequest, HeartbeatRequest, LogEntryRequest
from mediapipeline_desktop_app.network.registry import InFlightRegistry
from mediapipeline_desktop_app.network.share_block import (
    coerce_coordinator_port,
    format_coordinator_share_block,
    select_coordinator_share_ip,
)
from mediapipeline_desktop_app.network.threading_helpers import start_daemon_thread
from mediapipeline_desktop_app.network.worker_state import atomic_write_text, load_worker_state, save_worker_state
from mediapipeline_desktop_app.network.worker import (
    WorkerDispatcher,
    _atomic_write_text,
    _http_read_capped,
    _make_queue_record,
    _safe_hostname,
    _validate_coordinator_url,
)
from mediapipeline_desktop_app.network.worker_done import (
    build_completion_done_request,
    build_crash_recovery_done_request,
    build_release_done_request,
)
from mediapipeline_desktop_app.network.worker_record import make_queue_record


class NetworkProtocolRuntimeTests(unittest.TestCase):
    def test_heartbeat_request_progress_is_finite_and_clamped(self) -> None:
        self.assertEqual(HeartbeatRequest.from_dict({"progress_percent": -5}).progress_percent, 0.0)
        self.assertEqual(HeartbeatRequest.from_dict({"progress_percent": 125}).progress_percent, 100.0)
        self.assertEqual(HeartbeatRequest.from_dict({"progress_percent": "42.5"}).progress_percent, 42.5)
        with self.assertRaises(ValueError):
            HeartbeatRequest.from_dict({"progress_percent": float("nan")})
        with self.assertRaises(ValueError):
            HeartbeatRequest.from_dict({"progress_percent": float("inf")})

    def test_network_protocol_rejects_nonfinite_numeric_strings(self) -> None:
        with self.assertRaisesRegex(ValueError, "estimated_size_gb must be finite"):
            ClaimResponse.from_dict({"status": "ok", "estimated_size_gb": "NaN"})
        with self.assertRaisesRegex(ValueError, "retry_after_seconds must be >= 0"):
            ClaimResponse.from_dict({"status": "empty", "retry_after_seconds": -1})
        with self.assertRaisesRegex(ValueError, "elapsed_seconds must be finite"):
            DoneRequest.from_dict({"elapsed_seconds": "Infinity"})
        with self.assertRaisesRegex(ValueError, "output_size_bytes must be >= 0"):
            DoneRequest.from_dict({"output_size_bytes": -1})
        with self.assertRaisesRegex(ValueError, "fps must be finite"):
            HeartbeatRequest.from_dict({"fps": "NaN"})
        with self.assertRaisesRegex(ValueError, "eta_seconds must be >= 0"):
            HeartbeatRequest.from_dict({"eta_seconds": -1})

    def test_inflight_registry_heartbeat_clamps_progress_percent(self) -> None:
        registry = InFlightRegistry()
        registry.claim(
            job_id="job-1",
            worker_id="worker-1",
            worker_name="Worker",
            source_path=r"C:\Media\movie.mkv",
            encode_config={},
        )

        self.assertEqual(
            registry.heartbeat(
                "job-1",
                "worker-1",
                progress_percent=135,
                current_stage="encoding",
            ),
            "ok",
        )
        self.assertEqual(registry.snapshot()[0].progress_percent, 100.0)

    def test_inflight_registry_snapshot_sanitizes_bad_runtime_worker_stats(self) -> None:
        registry = InFlightRegistry()
        registry.claim(
            job_id="job-1",
            worker_id="worker-1",
            worker_name="Worker",
            source_path=r"C:\Media\movie.mkv",
            encode_config={},
        )
        with registry._lock:  # type: ignore[attr-defined]
            registry._worker_stats["worker-1"] = {  # type: ignore[attr-defined]
                "name": "Worker",
                "files": -1,
                "gb": float("nan"),
                "secs": "not-a-number",
            }
            registry._jobs["job-1"].progress_percent = float("nan")  # type: ignore[attr-defined]

        with self.assertLogs("mediapipeline_desktop_app.network.registry", level="WARNING") as logs:
            row = registry.snapshot()[0]

        self.assertEqual(row.files_completed, 0)
        self.assertEqual(row.total_gb_encoded, 0.0)
        self.assertEqual(row.avg_speed_gbh, 0.0)
        self.assertEqual(row.progress_percent, 0.0)
        text = "\n".join(logs.output)
        self.assertIn("Invalid worker stats files for worker-1", text)
        self.assertIn("Invalid worker stats gb for worker-1", text)
        self.assertIn("Invalid worker stats secs for worker-1", text)
        self.assertIn("Invalid worker progress for worker-1", text)

    def test_idle_workers_snapshot_sanitizes_bad_runtime_worker_stats(self) -> None:
        registry = InFlightRegistry()
        with registry._lock:  # type: ignore[attr-defined]
            registry._worker_stats["worker-2"] = "not-a-dict"  # type: ignore[attr-defined]

        with self.assertLogs("mediapipeline_desktop_app.network.registry", level="WARNING") as logs:
            row = registry.idle_workers_snapshot()[0]

        self.assertEqual(row.worker_id, "worker-2")
        self.assertEqual(row.worker_name, "worker-2"[:8])
        self.assertEqual(row.files_completed, 0)
        self.assertEqual(row.total_gb_encoded, 0.0)
        self.assertEqual(row.avg_speed_gbh, 0.0)
        self.assertIn("Malformed worker stats for worker-2", "\n".join(logs.output))

    def test_worker_reclaimed_heartbeat_updates_operator_status_and_aborts(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker.app = SimpleNamespace(snapshot=None)
        worker._worker_id = "worker-1"
        worker._heartbeat_stop = SimpleNamespace(wait=lambda _seconds: False)
        worker._http_post = lambda _path, _data: {"status": "reclaimed"}
        worker.log_cluster_event = lambda **_kwargs: None
        statuses: list[str] = []
        aborts: list[str] = []
        worker._notify_status = statuses.append
        worker._request_abort_reclaimed_job = lambda _job: aborts.append(_job.job_id)
        worker._job_reclaimed = False
        job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"))

        WorkerDispatcher._heartbeat_loop(worker, job)

        self.assertTrue(worker._job_reclaimed)
        self.assertEqual(statuses, ["⚠ Job reclaimed by coordinator — aborting movie.mkv"])
        self.assertEqual(aborts, ["job-1"])

    def test_worker_reclaimed_abort_schedule_failure_is_logged(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker.app = SimpleNamespace(_worker_abort_current_job=lambda: None)
        job = SimpleNamespace(job_id="job-1")

        def bad_post(_name: str, _callback: object) -> None:
            raise RuntimeError("ui queue offline")

        worker._post_app_callback = bad_post

        with self.assertLogs("mediapipeline_desktop_app.network.worker", level="ERROR") as logs:
            worker._request_abort_reclaimed_job(job)

        text = "\n".join(logs.output)
        self.assertIn("Failed to schedule abort for reclaimed job job-1", text)
        self.assertIn("ui queue offline", text)

    def test_worker_reclaimed_abort_schedule_failure_diagnostic_is_bounded(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker.app = SimpleNamespace(_worker_abort_current_job=lambda: None)
        job = SimpleNamespace(job_id="job-1")
        long_error = "ui queue offline " + ("x" * 500) + "tail-marker"

        def bad_post(_name: str, _callback: object) -> None:
            raise RuntimeError(long_error)

        worker._post_app_callback = bad_post

        with self.assertLogs("mediapipeline_desktop_app.network.worker", level="ERROR") as logs:
            worker._request_abort_reclaimed_job(job)

        text = "\n".join(logs.output)
        self.assertIn("Failed to schedule abort for reclaimed job job-1", text)
        self.assertIn("...<truncated>", text)
        self.assertNotIn("tail-marker", text)

    def test_worker_claim_record_helper_builds_synthetic_queue_record(self) -> None:
        claim = ClaimResponse(
            status="ok",
            job_id="job-1",
            source_path=r"C:\Media\Show\S01E01.mkv",
            priority=True,
            estimated_size_gb=1.25,
        )

        record = make_queue_record(claim)

        self.assertIs(_make_queue_record, make_queue_record)
        self.assertEqual(str(record.source_path), r"C:\Media\Show\S01E01.mkv")
        self.assertEqual(str(record.source_root), r"C:\Media\Show")
        self.assertEqual(record.display_name, "S01E01.mkv")
        self.assertEqual(record.sort_name, "S01E01")
        self.assertTrue(record.is_priority)
        self.assertEqual(record.size_gb, 1.25)
        self.assertEqual(record.route_name, "worker")
        self.assertEqual(record.phase, "WORKER")

    def test_worker_safe_cluster_event_logs_without_raising(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster offline"))  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline_desktop_app.network.worker", level="WARNING") as logs:
            WorkerDispatcher._safe_log_cluster_event(
                worker,
                "unit-test",
                level="INFO",
                event="test_event",
                job_id="job-123456",
            )

        output = "\n".join(logs.output)
        self.assertIn("Failed to emit unit-test cluster event for job job-1234", output)
        self.assertIn("cluster offline", output)

    def test_worker_claim_record_invalid_cluster_log_failure_still_releases_claim(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._poll_stop = threading.Event()
        worker._active_job_lock = threading.Lock()
        worker._active_job = None
        worker._worker_id = "worker-1"
        worker._worker_name = "worker-box"
        worker._poll_interval = 30
        claim = ClaimResponse(
            status="ok",
            job_id="job-1",
            source_path=r"C:\Media\bad.mkv",
            estimated_size_gb=1.0,
        )
        worker._http_get = lambda _path, _params: claim.to_dict()  # type: ignore[method-assign]
        worker._apply_path_map = lambda path: path  # type: ignore[method-assign]
        worker.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster offline"))  # type: ignore[method-assign]
        releases: list[tuple[str, str]] = []
        worker._release_unstartable_claim = lambda released_claim, reason: releases.append((released_claim.job_id, reason))  # type: ignore[method-assign]
        worker._wait_interruptible = lambda *_args: worker._poll_stop.set()  # type: ignore[method-assign]

        with (
            patch("mediapipeline_desktop_app.network.worker._make_queue_record", side_effect=RuntimeError("record invalid")),
            self.assertLogs("mediapipeline_desktop_app.network.worker", level="WARNING") as logs,
        ):
            WorkerDispatcher._poll_loop(worker)

        self.assertEqual(releases, [("job-1", "record invalid")])
        self.assertIn("Failed to emit claim-record-invalid cluster event for job job-1", "\n".join(logs.output))

    def test_worker_claim_record_invalid_diagnostic_is_bounded(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._poll_stop = threading.Event()
        worker._active_job_lock = threading.Lock()
        worker._active_job = None
        worker._worker_id = "worker-1"
        worker._worker_name = "worker-box"
        worker._poll_interval = 30
        long_error = "record invalid " + ("x" * 500) + "tail-marker"
        claim = ClaimResponse(
            status="ok",
            job_id="job-1",
            source_path=r"C:\Media\bad.mkv",
            estimated_size_gb=1.0,
        )
        worker._http_get = lambda _path, _params: claim.to_dict()  # type: ignore[method-assign]
        worker._apply_path_map = lambda path: path  # type: ignore[method-assign]
        events: list[dict[str, object]] = []
        releases: list[tuple[str, str]] = []
        worker.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[method-assign]
        worker._release_unstartable_claim = lambda released_claim, reason: releases.append((released_claim.job_id, reason))  # type: ignore[method-assign]
        worker._wait_interruptible = lambda *_args: worker._poll_stop.set()  # type: ignore[method-assign]

        with (
            patch("mediapipeline_desktop_app.network.worker._make_queue_record", side_effect=RuntimeError(long_error)),
            self.assertLogs("mediapipeline_desktop_app.network.worker", level="ERROR") as logs,
        ):
            WorkerDispatcher._poll_loop(worker)

        output = "\n".join(logs.output)
        self.assertIn("Failed to build QueueRecord for claimed job", output)
        self.assertIn("...<truncated>", output)
        self.assertNotIn("tail-marker", output)
        self.assertEqual(events[0]["event"], "claim_record_invalid")
        self.assertIn("...<truncated>", str(events[0]["message"]))
        self.assertNotIn("tail-marker", str(events[0]["message"]))
        self.assertEqual(releases[0][0], "job-1")
        self.assertIn("...<truncated>", releases[0][1])
        self.assertNotIn("tail-marker", releases[0][1])

    def test_worker_path_remap_cluster_log_failure_still_hands_off_claim(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._poll_stop = threading.Event()
        worker._active_job_lock = threading.Lock()
        worker._active_job = None
        worker._worker_id = "worker-1"
        worker._worker_name = "worker-box"
        worker._poll_interval = 30
        original = r"\\SERVER\Media\movie.mkv"
        mapped = r"D:\Media\movie.mkv"
        claim = ClaimResponse(
            status="ok",
            job_id="job-1",
            source_path=original,
            estimated_size_gb=1.0,
        )
        worker._http_get = lambda _path, _params: claim.to_dict()  # type: ignore[method-assign]
        worker._apply_path_map = lambda _path: mapped  # type: ignore[method-assign]
        worker.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster offline"))  # type: ignore[method-assign]
        handed_off: list[str] = []
        worker._on_job_claimed = lambda job: handed_off.append(str(job.record.source_path))  # type: ignore[method-assign]
        worker._wait_interruptible = lambda *_args: worker._poll_stop.set()  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline_desktop_app.network.worker", level="WARNING") as logs:
            WorkerDispatcher._poll_loop(worker)

        self.assertEqual(handed_off, [mapped])
        self.assertEqual(worker._active_job.record.source_path, Path(mapped))
        self.assertIn("Failed to emit path-remapped cluster event for job job-1", "\n".join(logs.output))

    def test_worker_done_request_builders_preserve_completion_semantics(self) -> None:
        crash = build_crash_recovery_done_request("job-1", "worker-1")
        self.assertEqual(crash.job_id, "job-1")
        self.assertEqual(crash.worker_id, "worker-1")
        self.assertFalse(crash.success)
        self.assertEqual(crash.error_message, "Worker crashed or restarted")

        released = build_release_done_request("job-2", "worker-1")
        self.assertFalse(released.success)
        self.assertTrue(released.released)

        job = SimpleNamespace(job_id="job-3", encode_config={"__retry_on_failure": True})
        done = build_completion_done_request(
            job,
            "worker-1",
            success=True,
            output_path=r"C:\out\movie.mkv",
            elapsed_seconds=12.5,
            output_size_bytes=123,
            completion_status="ok",
            publish_state="published",
            publish_mode="direct",
            route="remux",
        )
        self.assertTrue(done.success)
        self.assertEqual(done.output_path, r"C:\out\movie.mkv")
        self.assertEqual(done.elapsed_seconds, 12.5)
        self.assertEqual(done.output_size_bytes, 123)
        self.assertEqual(done.completion_status, "ok")
        self.assertEqual(done.publish_state, "published")
        self.assertEqual(done.publish_mode, "direct")
        self.assertEqual(done.route, "remux")
        self.assertTrue(done.retry_on_failure)

        terminal = build_completion_done_request(job, "worker-1", success=False, queue_terminal=True)
        self.assertTrue(terminal.queue_terminal)
        self.assertFalse(terminal.retry_on_failure)

        non_retry_job = SimpleNamespace(job_id="job-4", encode_config={"__retry_on_failure": False})
        failed = build_completion_done_request(non_retry_job, "worker-1", success=False)
        self.assertFalse(failed.retry_on_failure)

    def test_worker_poll_policy_clamps_retry_hints(self) -> None:
        self.assertEqual(resolve_worker_wait_seconds(None, 30), 30.0)
        self.assertEqual(resolve_worker_wait_seconds(0, 30), 30.0)
        self.assertEqual(resolve_worker_wait_seconds(-5, 30), 30.0)
        self.assertEqual(resolve_worker_wait_seconds(5, 30), 5.0)
        self.assertEqual(resolve_worker_wait_seconds(600, 30), 30.0)
        self.assertEqual(resolve_worker_wait_seconds(1, 30), 1.0)

    def test_worker_poll_interval_coercion_handles_malformed_config(self) -> None:
        self.assertEqual(resolve_worker_poll_interval(None), 30)
        self.assertEqual(resolve_worker_poll_interval("6"), 6)
        with self.assertLogs("mediapipeline_desktop_app.network.poll_policy", level="WARNING") as logs:
            self.assertEqual(resolve_worker_poll_interval("not-a-number"), 30)
            self.assertEqual(resolve_worker_poll_interval("0"), 5)
            self.assertEqual(resolve_worker_poll_interval("-5"), 5)
            self.assertEqual(resolve_worker_poll_interval("4"), 5)
        combined = "\n".join(logs.output)
        self.assertIn("Invalid WorkerPollIntervalSecs", combined)
        self.assertIn("below 5", combined)



if __name__ == "__main__":
    unittest.main()
