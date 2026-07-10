from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from types import SimpleNamespace

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.network.protocol import ClaimResponse, DoneRequest
from mediapipeline.desktop.network.worker_state import (
    load_pending_done_report,
    load_worker_state,
    pending_done_reports_dir,
)
from mediapipeline.desktop.network.worker import WorkerDispatcher


class NetworkDoneReleaseTests(unittest.TestCase):
    def _single_pending_report(self, state_path: Path) -> dict:
        reports = list(pending_done_reports_dir(state_path).glob("*.json"))
        self.assertEqual(len(reports), 1)
        return load_pending_done_report(reports[0])

    def test_worker_mark_done_posts_terminal_payload_and_clears_active_job(self) -> None:
        posts: list[tuple[str, dict]] = []
        events: list[dict] = []
        clears: list[bool] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_id = "worker-1"
        worker._active_job_lock = threading.Lock()
        worker._active_job = object()
        worker._stop_heartbeat = lambda: None
        worker._clear_worker_state = lambda: clears.append(True)
        worker._http_post = lambda post_path, data: posts.append((post_path, data)) or {}
        worker.log_cluster_event = lambda **kwargs: events.append(kwargs)

        job = SimpleNamespace(
            job_id="job-1",
            encode_config={"__retry_on_failure": True},
            record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"),
        )

        with self.assertLogs("mediapipeline.desktop.network.worker", level="INFO") as logs:
            WorkerDispatcher.mark_done(
                worker,
                job,
                success=False,
                elapsed_seconds=42.0,
                error="ocr failed",
                completion_status="manual_review",
                queue_terminal=True,
                route="subtitle_srt",
            )

        self.assertIsNone(worker._active_job)
        self.assertEqual(posts[0][0], "/api/done")
        payload = posts[0][1]
        self.assertEqual(payload["job_id"], "job-1")
        self.assertEqual(payload["worker_id"], "worker-1")
        self.assertFalse(payload["success"])
        self.assertEqual(payload["elapsed_seconds"], 42.0)
        self.assertEqual(payload["error_message"], "ocr failed")
        self.assertEqual(payload["completion_status"], "manual_review")
        self.assertTrue(payload["queue_terminal"])
        self.assertFalse(payload["retry_on_failure"])
        self.assertEqual(payload["route"], "subtitle_srt")
        self.assertEqual(events[0]["event"], "encode_terminal")
        self.assertEqual(clears, [True])
        joined_logs = "\n".join(logs.output)
        self.assertIn("Job job-1 failed report accepted by coordinator.", joined_logs)
        self.assertNotIn("Job job-1 reported failed.", joined_logs)

    def test_worker_mark_done_honors_explicit_retryability(self) -> None:
        posts: list[tuple[str, dict]] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_id = "worker-1"
        worker._active_job_lock = threading.Lock()
        worker._active_job = object()
        worker._stop_heartbeat = lambda: None
        worker._clear_worker_state = lambda: None
        worker._http_post = lambda post_path, data: posts.append((post_path, data)) or {}
        worker.log_cluster_event = lambda **_kwargs: None
        job = SimpleNamespace(
            job_id="job-1",
            encode_config={"__retry_on_failure": True},
            record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"),
        )

        WorkerDispatcher.mark_done(
            worker,
            job,
            success=False,
            elapsed_seconds=3.0,
            completion_status="failed",
            queue_terminal=False,
            retry_on_failure=False,
            reason_code="ENCODE_ERROR",
            reason="child result marked retryable false",
        )

        payload = posts[0][1]
        self.assertFalse(payload["queue_terminal"])
        self.assertFalse(payload["retry_on_failure"])

    def test_worker_mark_done_post_failure_updates_operator_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "worker_state.json"
            statuses: list[str] = []
            events: list[dict] = []
            clears: list[bool] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = state_path
            worker._worker_id = "worker-1"
            worker._active_job_lock = threading.Lock()
            worker._active_job = object()
            worker._status_callback = statuses.append
            worker._stop_heartbeat = lambda: None
            worker._clear_worker_state = lambda: clears.append(True)
            worker._http_post = lambda _post_path, _data: (_ for _ in ()).throw(RuntimeError("coordinator offline"))
            worker.log_cluster_event = lambda **kwargs: events.append(kwargs)

            job = SimpleNamespace(
                job_id="job-1",
                encode_config={},
                record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"),
            )

            with self.assertLogs("mediapipeline.desktop.network.worker", level="INFO") as logs:
                WorkerDispatcher.mark_done(worker, job, success=True, elapsed_seconds=42.0)

            self.assertIsNone(worker._active_job)
            self.assertEqual(statuses, ["⚠ Done report failed: coordinator offline"])
            self.assertEqual(events[0]["event"], "encode_done")
            self.assertEqual(clears, [True])
            report = self._single_pending_report(state_path)
            self.assertEqual(report["job_id"], "job-1")
            self.assertTrue(report["success"])
            joined_logs = "\n".join(logs.output)
            self.assertIn("Job job-1 completion report pending retry after coordinator POST failure.", joined_logs)
            self.assertNotIn("Job job-1 reported done.", joined_logs)

    def test_worker_mark_done_cleanup_failure_after_accepted_report_does_not_save_pending(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "worker_state.json"
            pending_saves: list[dict] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = state_path
            worker._worker_id = "worker-1"
            worker._active_job_lock = threading.Lock()
            worker._active_job = object()
            worker._stop_heartbeat = lambda: None
            worker._http_post = lambda _post_path, _data: {}
            worker._clear_worker_state = lambda: (_ for _ in ()).throw(RuntimeError("cleanup offline"))  # type: ignore[method-assign]
            worker._save_pending_done_report = lambda _job, payload: pending_saves.append(payload)  # type: ignore[method-assign]
            worker.log_cluster_event = lambda **_kwargs: None
            job = SimpleNamespace(
                job_id="job-1",
                encode_config={},
                record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"),
            )

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                WorkerDispatcher.mark_done(worker, job, success=True, elapsed_seconds=42.0)

            self.assertEqual(pending_saves, [])
            text = "\n".join(logs.output)
            self.assertIn("Coordinator accepted done report for job job-1", text)
            self.assertIn("not saving a pending done report", text)

    def test_worker_release_posts_clean_release_payload(self) -> None:
        posts: list[tuple[str, dict]] = []
        events: list[dict] = []
        clears: list[bool] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_id = "worker-1"
        worker._active_job_lock = threading.Lock()
        worker._active_job = object()
        worker._stop_heartbeat = lambda: None
        worker._clear_worker_state = lambda: clears.append(True)
        worker._http_post = lambda post_path, data: posts.append((post_path, data)) or {}
        worker.log_cluster_event = lambda **kwargs: events.append(kwargs)

        job = SimpleNamespace(
            job_id="job-2",
            encode_config={},
            record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"),
        )

        with self.assertLogs("mediapipeline.desktop.network.worker", level="INFO") as logs:
            WorkerDispatcher.release(worker, job)

        self.assertIsNone(worker._active_job)
        self.assertEqual(posts[0][0], "/api/done")
        payload = posts[0][1]
        self.assertEqual(payload["job_id"], "job-2")
        self.assertEqual(payload["worker_id"], "worker-1")
        self.assertFalse(payload["success"])
        self.assertTrue(payload["released"])
        self.assertTrue(payload["retry_on_failure"])
        self.assertEqual(events[0]["event"], "job_released")
        self.assertEqual(clears, [True])
        joined_logs = "\n".join(logs.output)
        self.assertIn("Job job-2 release report accepted by coordinator.", joined_logs)
        self.assertNotIn("Job job-2 released.", joined_logs)

    def test_worker_release_post_failure_updates_operator_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "worker_state.json"
            statuses: list[str] = []
            events: list[dict] = []
            clears: list[bool] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = state_path
            worker._worker_id = "worker-1"
            worker._active_job_lock = threading.Lock()
            worker._active_job = object()
            worker._status_callback = statuses.append
            worker._stop_heartbeat = lambda: None
            worker._clear_worker_state = lambda: clears.append(True)
            worker._http_post = lambda _post_path, _data: (_ for _ in ()).throw(RuntimeError("coordinator offline"))
            worker.log_cluster_event = lambda **kwargs: events.append(kwargs)

            job = SimpleNamespace(
                job_id="job-2",
                encode_config={},
                record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"),
            )

            with self.assertLogs("mediapipeline.desktop.network.worker", level="INFO") as logs:
                WorkerDispatcher.release(worker, job)

            self.assertIsNone(worker._active_job)
            self.assertEqual(statuses, ["⚠ Release report failed: coordinator offline"])
            self.assertEqual(events[0]["event"], "job_released")
            self.assertEqual(clears, [True])
            report = self._single_pending_report(state_path)
            self.assertEqual(report["job_id"], "job-2")
            self.assertTrue(report["released"])
            joined_logs = "\n".join(logs.output)
            self.assertIn("Job job-2 release report pending retry after coordinator POST failure.", joined_logs)
            self.assertNotIn("Job job-2 released.", joined_logs)

    def test_worker_release_cleanup_failure_after_accepted_report_does_not_save_pending(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "worker_state.json"
            pending_saves: list[dict] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = state_path
            worker._worker_id = "worker-1"
            worker._active_job_lock = threading.Lock()
            worker._active_job = object()
            worker._stop_heartbeat = lambda: None
            worker._http_post = lambda _post_path, _data: {}
            worker._clear_worker_state = lambda: (_ for _ in ()).throw(RuntimeError("cleanup offline"))  # type: ignore[method-assign]
            worker._save_pending_done_report = lambda _job, payload: pending_saves.append(payload)  # type: ignore[method-assign]
            worker.log_cluster_event = lambda **_kwargs: None
            job = SimpleNamespace(
                job_id="job-2",
                encode_config={},
                record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"),
            )

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                WorkerDispatcher.release(worker, job)

            self.assertEqual(pending_saves, [])
            text = "\n".join(logs.output)
            self.assertIn("Coordinator accepted release report for job job-2", text)
            self.assertIn("not saving a pending done report", text)

    def test_worker_internal_release_failure_updates_operator_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "worker_state.json"
            statuses: list[str] = []
            clears: list[bool] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = state_path
            worker._worker_id = "worker-1"
            worker._active_job_lock = threading.Lock()
            worker._active_job = object()
            worker._status_callback = statuses.append
            worker._stop_heartbeat = lambda: None
            worker._clear_worker_state = lambda: clears.append(True)
            worker._http_post = lambda _post_path, _data: (_ for _ in ()).throw(RuntimeError("coordinator offline"))

            job = SimpleNamespace(
                job_id="job-3",
                encode_config={},
                record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"),
            )

            with self.assertLogs("mediapipeline.desktop.network.worker", level="INFO") as logs:
                WorkerDispatcher._do_release(worker, job)

            self.assertIsNone(worker._active_job)
            self.assertEqual(statuses, ["⚠ Release report failed: coordinator offline"])
            self.assertEqual(clears, [True])
            report = self._single_pending_report(state_path)
            self.assertEqual(report["job_id"], "job-3")
            self.assertTrue(report["released"])
            text = "\n".join(logs.output)
            self.assertIn("POST /api/done (internal release) failed", text)
            self.assertIn("Job job-3 internal release report pending retry after coordinator POST failure.", text)

    def test_worker_report_logs_when_pending_retry_save_fails(self) -> None:
        def make_worker() -> WorkerDispatcher:
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._worker_id = "worker-1"
            worker._active_job_lock = threading.Lock()
            worker._active_job = object()
            worker._stop_heartbeat = lambda: None  # type: ignore[method-assign]
            worker._http_post = lambda _post_path, _data: (_ for _ in ()).throw(RuntimeError("coordinator offline"))  # type: ignore[method-assign]
            worker._save_pending_done_report = lambda _job, _payload: False  # type: ignore[method-assign]
            worker.log_cluster_event = lambda **_kwargs: None  # type: ignore[method-assign]
            return worker

        cases = (
            (
                "completion",
                lambda worker, job: WorkerDispatcher.mark_done(worker, job, success=True, elapsed_seconds=42.0),
                "Job job-6 completion report could not be saved for pending retry after coordinator POST failure.",
                "Job job-6 completion report pending retry after coordinator POST failure.",
            ),
            (
                "release",
                lambda worker, job: WorkerDispatcher.release(worker, job),
                "Job job-6 release report could not be saved for pending retry after coordinator POST failure.",
                "Job job-6 release report pending retry after coordinator POST failure.",
            ),
            (
                "internal release",
                lambda worker, job: WorkerDispatcher._do_release(worker, job),
                "Job job-6 internal release report could not be saved for pending retry after coordinator POST failure.",
                "Job job-6 internal release report pending retry after coordinator POST failure.",
            ),
        )

        for name, runner, expected, stale in cases:
            with self.subTest(name=name):
                worker = make_worker()
                job = SimpleNamespace(
                    job_id="job-6",
                    encode_config={},
                    record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"),
                )

                with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                    runner(worker, job)

                text = "\n".join(logs.output)
                self.assertIn(expected, text)
                self.assertNotIn(stale, text)

    def test_worker_done_post_failure_diagnostics_are_bounded(self) -> None:
        long_error = "coordinator offline " + ("x" * 500) + "tail-marker"

        def make_worker(statuses: list[str]) -> WorkerDispatcher:
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._worker_id = "worker-1"
            worker._active_job_lock = threading.Lock()
            worker._active_job = object()
            worker._status_callback = statuses.append
            worker._stop_heartbeat = lambda: None  # type: ignore[method-assign]
            worker._http_post = lambda _post_path, _data: (_ for _ in ()).throw(RuntimeError(long_error))  # type: ignore[method-assign]
            worker._save_pending_done_report = lambda _job, _payload: True  # type: ignore[method-assign]
            worker.log_cluster_event = lambda **_kwargs: None  # type: ignore[method-assign]
            return worker

        cases = (
            (
                "completion",
                lambda worker, job: WorkerDispatcher.mark_done(worker, job, success=True, elapsed_seconds=42.0),
                "POST /api/done failed",
                "⚠ Done report failed:",
            ),
            (
                "release",
                lambda worker, job: WorkerDispatcher.release(worker, job),
                "POST /api/done (release) failed",
                "⚠ Release report failed:",
            ),
            (
                "internal release",
                lambda worker, job: WorkerDispatcher._do_release(worker, job),
                "POST /api/done (internal release) failed",
                "⚠ Release report failed:",
            ),
        )

        for name, runner, log_prefix, status_prefix in cases:
            with self.subTest(name=name):
                statuses: list[str] = []
                worker = make_worker(statuses)
                job = SimpleNamespace(
                    job_id="job-7",
                    encode_config={},
                    record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"),
                )

                with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                    runner(worker, job)

                text = "\n".join(logs.output)
                self.assertIn(log_prefix, text)
                self.assertIn("...<truncated>", text)
                self.assertNotIn("tail-marker", text)
                self.assertEqual(len(statuses), 1)
                self.assertTrue(statuses[0].startswith(status_prefix))
                self.assertNotIn("tail-marker", statuses[0])

    def test_worker_internal_release_logs_accepted_report(self) -> None:
        posts: list[tuple[str, dict]] = []
        clears: list[bool] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_id = "worker-1"
        worker._active_job_lock = threading.Lock()
        worker._active_job = object()
        worker._stop_heartbeat = lambda: None
        worker._clear_worker_state = lambda: clears.append(True)
        worker._http_post = lambda post_path, data: posts.append((post_path, data)) or {}
        job = SimpleNamespace(
            job_id="job-3",
            encode_config={},
            record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"),
        )

        with self.assertLogs("mediapipeline.desktop.network.worker", level="INFO") as logs:
            WorkerDispatcher._do_release(worker, job)

        self.assertIsNone(worker._active_job)
        self.assertEqual(posts[0][0], "/api/done")
        self.assertEqual(posts[0][1]["job_id"], "job-3")
        self.assertTrue(posts[0][1]["released"])
        self.assertEqual(clears, [True])
        self.assertIn("Job job-3 internal release report accepted by coordinator.", "\n".join(logs.output))

    def test_worker_internal_release_cleanup_failure_after_accepted_report_does_not_save_pending(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "worker_state.json"
            pending_saves: list[dict] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = state_path
            worker._worker_id = "worker-1"
            worker._active_job_lock = threading.Lock()
            worker._active_job = object()
            worker._stop_heartbeat = lambda: None
            worker._http_post = lambda _post_path, _data: {}
            worker._clear_worker_state = lambda: (_ for _ in ()).throw(RuntimeError("cleanup offline"))  # type: ignore[method-assign]
            worker._save_pending_done_report = lambda _job, payload: pending_saves.append(payload)  # type: ignore[method-assign]
            job = SimpleNamespace(
                job_id="job-3",
                encode_config={},
                record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"),
            )

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                WorkerDispatcher._do_release(worker, job)

            self.assertEqual(pending_saves, [])
            text = "\n".join(logs.output)
            self.assertIn("Coordinator accepted internal release report for job job-3", text)
            self.assertIn("not saving a pending done report", text)

    def test_worker_releases_unstartable_claim_to_avoid_stale_timeout_wait(self) -> None:
        statuses: list[str] = []
        posts: list[tuple[str, dict]] = []
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._worker_id = "worker-1"
        worker._status_callback = statuses.append
        worker._http_post = lambda post_path, data: posts.append((post_path, data)) or {}
        claim = ClaimResponse(job_id="job-4", source_path=r"C:\Media\bad.mkv")

        WorkerDispatcher._release_unstartable_claim(worker, claim, "record build failed")

        self.assertEqual(posts[0][0], "/api/done")
        self.assertEqual(posts[0][1]["job_id"], "job-4")
        self.assertTrue(posts[0][1]["released"])
        self.assertEqual(statuses, ["⚠ Released unstartable claim: record build failed"])

    def test_worker_unstartable_claim_release_failure_updates_operator_status(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "worker_state.json"
            statuses: list[str] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = state_path
            worker._worker_id = "worker-1"
            worker._status_callback = statuses.append
            worker._http_post = lambda _post_path, _data: (_ for _ in ()).throw(RuntimeError("coordinator offline"))
            claim = ClaimResponse(job_id="job-5", source_path=r"C:\Media\bad.mkv")

            WorkerDispatcher._release_unstartable_claim(worker, claim, "record build failed")

            state = load_worker_state(state_path)

        self.assertEqual(statuses, ["⚠ Release report queued for retry: coordinator offline"])
        self.assertEqual(state["job_id"], "job-5")
        self.assertTrue(state["pending_done_report"]["released"])

    def test_worker_unstartable_claim_release_failure_bounds_reason_text(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            statuses: list[str] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = Path(td) / "worker_state.json"
            worker._worker_id = "worker-1"
            worker._status_callback = statuses.append
            worker._http_post = lambda _post_path, _data: (_ for _ in ()).throw(RuntimeError("coordinator offline"))
            claim = ClaimResponse(job_id="job-5", source_path=r"C:\Media\bad.mkv")
            reason = "record build failed: " + ("x" * 500) + "tail-marker"

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                WorkerDispatcher._release_unstartable_claim(worker, claim, reason)

        output = "\n".join(logs.output)
        self.assertIn("...<truncated>", output)
        self.assertNotIn("tail-marker", output)
        self.assertEqual(statuses, ["⚠ Release report queued for retry: coordinator offline"])

    def test_worker_unstartable_claim_release_failure_bounds_post_error_text(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            statuses: list[str] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = Path(td) / "worker_state.json"
            worker._worker_id = "worker-1"
            worker._status_callback = statuses.append
            long_error = "coordinator offline " + ("x" * 500) + "tail-marker"
            worker._http_post = lambda _post_path, _data: (_ for _ in ()).throw(RuntimeError(long_error))
            claim = ClaimResponse(job_id="job-5", source_path=r"C:\Media\bad.mkv")

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                WorkerDispatcher._release_unstartable_claim(worker, claim, "record build failed")

        output = "\n".join(logs.output)
        self.assertIn("...<truncated>", output)
        self.assertNotIn("tail-marker", output)
        self.assertEqual(len(statuses), 1)
        self.assertIn("Release report queued for retry", statuses[0])
        self.assertNotIn("tail-marker", statuses[0])

    def test_done_request_preserves_completion_publish_and_queue_terminal_fields(self) -> None:
        request = DoneRequest(
            job_id="job-1",
            worker_id="worker-1",
            success=False,
            output_path=r"C:\Media\Out\Movie.mkv",
            output_size_bytes=123,
            completion_status="skipped",
            publish_state="pending_publish",
            publish_mode="deferred",
            route="remux",
            queue_terminal=True,
            retry_on_failure=False,
        )

        round_tripped = DoneRequest.from_dict(request.to_dict())

        self.assertEqual(round_tripped.completion_status, "skipped")
        self.assertEqual(round_tripped.publish_state, "pending_publish")
        self.assertEqual(round_tripped.publish_mode, "deferred")
        self.assertEqual(round_tripped.route, "remux")
        self.assertTrue(round_tripped.queue_terminal)
        self.assertFalse(round_tripped.retry_on_failure)
