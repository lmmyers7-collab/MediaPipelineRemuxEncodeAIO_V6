from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
import os
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.status.runtime_health import runtime_reliability_counters
from mediapipeline.desktop.network.worker_state import (
    atomic_write_text,
    iter_pending_done_report_files,
    load_pending_done_report,
    load_worker_state,
    pending_done_reports_review_dir,
    queue_pending_done_report,
    save_worker_state,
    worker_state_backup_path,
)
from mediapipeline.desktop.network.worker import WorkerDispatcher, _atomic_write_text


class NetworkWorkerStateTests(unittest.TestCase):
    def test_atomic_write_text_replaces_complete_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"

            _atomic_write_text(path, "first\n")
            _atomic_write_text(path, "second\n")

            self.assertEqual(path.read_text(encoding="utf-8"), "second\n")
            leftovers = [p for p in path.parent.iterdir() if p.suffix == ".tmp"]
            self.assertEqual(leftovers, [])

    def test_worker_state_helpers_round_trip_job_identity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"

            save_worker_state(path, job_id="job-1", source_path=r"C:\Media\movie.mkv")
            state = load_worker_state(path)

            self.assertEqual(state["job_id"], "job-1")
            self.assertEqual(state["source_path"], r"C:\Media\movie.mkv")
            self.assertNotIn("pending_done_report", state)

    def test_worker_state_save_failure_updates_status_and_cluster_log(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._state_path = Path("worker_state.json")
        statuses: list[str] = []
        events: list[dict] = []
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker._safe_log_cluster_event = lambda context, **kwargs: events.append({"context": context, **kwargs})  # type: ignore[method-assign]
        job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"))

        with (
            patch("mediapipeline.desktop.network.worker_state.save_worker_state", side_effect=OSError("disk full")),
            self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs,
        ):
            with self.assertRaises(OSError):
                WorkerDispatcher._save_worker_state(worker, job)  # type: ignore[arg-type]

        self.assertEqual(statuses, ["⚠ Worker crash recovery state save failed - check logs."])
        self.assertEqual(events[0]["context"], "worker-state-save-failed")
        self.assertEqual(events[0]["event"], "worker_state_save_failed")
        self.assertEqual(events[0]["job_id"], "job-1")
        self.assertEqual(events[0]["source_path"], r"C:\Media\movie.mkv")
        self.assertIn("Failed to save worker_state.json for job job-1: disk full", "\n".join(logs.output))

    def test_worker_state_helpers_round_trip_pending_done_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            pending = {"job_id": "job-1", "worker_id": "worker-1", "success": True}

            save_worker_state(
                path,
                job_id="job-1",
                source_path=r"C:\Media\movie.mkv",
                pending_done_report=pending,
            )
            state = load_worker_state(path)

            self.assertEqual(state["pending_done_report"], pending)

    def test_runtime_health_reports_pending_done_oldest_age_and_blocked_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            state_root = root / "State"
            app_state = state_root / "App"
            queued_dir = app_state / "pending_done_reports"
            queued_dir.mkdir(parents=True)
            now = datetime(2026, 6, 18, 12, 0, tzinfo=timezone.utc)
            report_path = queued_dir / "job-1.json"
            report_path.write_text(json.dumps({"job_id": "job-1", "success": True}), encoding="utf-8")
            old_mtime = (now - timedelta(hours=3)).timestamp()
            os.utime(report_path, (old_mtime, old_mtime))
            resolved = SimpleNamespace(
                state_root=state_root,
                app_state_path=app_state / "worker_state.json",
                progress_file=state_root / "Progress" / "pipeline_progress.json",
                pending_push_path=state_root / "PendingServerPush",
                active_jobs_path=state_root / "ActiveJobs",
                log_file=root / "LocalBase" / "pipeline_debug.log",
                config_data={},
            )

            counters = runtime_reliability_counters(resolved, now=now)

        reports = counters["worker_pending_reports"]
        self.assertEqual(reports["pending_report_count"], 1)
        self.assertEqual(reports["oldest_pending_report_age_seconds"], 10800)
        self.assertTrue(reports["blocked"])
        self.assertEqual(reports["block_reason"], "pending_done_reports_present")

    def test_pending_done_report_save_failure_updates_status_and_cluster_log(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._state_path = Path("worker_state.json")
        statuses: list[str] = []
        events: list[dict] = []
        worker._notify_status = statuses.append  # type: ignore[method-assign]
        worker._safe_log_cluster_event = lambda context, **kwargs: events.append({"context": context, **kwargs})  # type: ignore[method-assign]
        job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"))
        payload = {"job_id": "job-1", "worker_id": "worker-1", "success": True}

        with (
            patch("mediapipeline.desktop.network.worker_state.queue_pending_done_report", side_effect=OSError("disk full")),
            self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs,
        ):
            saved = WorkerDispatcher._save_pending_done_report(worker, job, payload)  # type: ignore[arg-type]

        self.assertFalse(saved)
        self.assertEqual(statuses, ["⚠ Pending done-report retry save failed - check logs."])
        self.assertEqual(events[0]["context"], "pending-done-save-failed")
        self.assertEqual(events[0]["event"], "pending_done_save_failed")
        self.assertEqual(events[0]["job_id"], "job-1")
        self.assertEqual(events[0]["source_path"], r"C:\Media\movie.mkv")
        self.assertIn("Failed to save pending done report for job job-1: disk full", "\n".join(logs.output))

    def test_worker_state_load_rejects_nonfinite_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            path.write_text('{"job_id": "job-1", "source_path": NaN}', encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "worker_state.json was corrupt and quarantined"):
                load_worker_state(path)

            self.assertFalse(path.exists())

    def test_worker_state_load_recovers_corrupt_main_from_backup(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            backup = worker_state_backup_path(path)
            backup.write_text('{"job_id": "job-backup", "source_path": "C:/Media/backup.mkv"}', encoding="utf-8")
            path.write_text("{not json", encoding="utf-8")

            state = load_worker_state(path)

            self.assertEqual(state["job_id"], "job-backup")
            self.assertEqual(load_worker_state(path)["job_id"], "job-backup")
            quarantined = list((path.parent / "worker_state_review").glob("*.json"))
            self.assertEqual(len(quarantined), 1)

    def test_worker_state_rejects_nonfinite_pending_done_json(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"

            with self.assertRaises(ValueError):
                save_worker_state(
                    path,
                    job_id="job-1",
                    source_path=r"C:\Media\movie.mkv",
                    pending_done_report={"elapsed_seconds": float("nan")},
                )

            self.assertFalse(path.exists())

    def test_worker_state_atomic_write_logs_temp_cleanup_failure_after_save_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"

            with (
                patch("mediapipeline.desktop.network.worker_state.os.replace", side_effect=OSError("replace denied")),
                patch("pathlib.Path.unlink", side_effect=OSError("cleanup denied")),
                self.assertLogs("mediapipeline.desktop.network.worker_state", level="WARNING") as logs,
            ):
                with self.assertRaisesRegex(OSError, "replace denied"):
                    atomic_write_text(path, "{}\n")

        combined = "\n".join(logs.output)
        self.assertIn("Failed to remove temporary worker state file", combined)
        self.assertIn("cleanup denied", combined)

    def test_worker_clear_state_failure_is_operator_visible(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._state_path = Path("worker_state.json")

        with (
            patch("mediapipeline.desktop.network.worker_state.clear_worker_state", side_effect=OSError("unlink denied")),
            self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs,
        ):
            cleared = WorkerDispatcher._clear_worker_state(worker)

        self.assertFalse(cleared)
        combined = "\n".join(logs.output)
        self.assertIn("Failed to clear worker_state.json after coordinator state transition", combined)
        self.assertIn("unlink denied", combined)

    def test_accepted_report_cleanup_logs_context_when_guarded_clear_returns_false(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._state_path = Path("worker_state.json")

        with (
            patch("mediapipeline.desktop.network.worker_state.clear_worker_state", side_effect=OSError("unlink denied")),
            self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs,
        ):
            WorkerDispatcher._clear_worker_state_after_accepted_report(worker, "job-1", "done")

        combined = "\n".join(logs.output)
        self.assertIn("Failed to clear worker_state.json after coordinator state transition", combined)
        self.assertIn("Coordinator accepted done report for job job-1", combined)
        self.assertIn("not saving a pending done report", combined)


class WorkerPendingDoneFlushTests(unittest.TestCase):
    def _make_worker(
        self,
        state_path: Path,
        posts: list[tuple[str, dict]],
        events: list[dict],
        post_error: Exception | None = None,
    ) -> WorkerDispatcher:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._state_path = state_path
        worker._worker_id = "worker-1"
        worker._safe_log_cluster_event = lambda context, **kwargs: events.append({"context": context, **kwargs})  # type: ignore[method-assign]

        def _post(path: str, payload: dict) -> dict:
            if post_error is not None:
                raise post_error
            posts.append((path, payload))
            return {}

        worker._http_post = _post  # type: ignore[method-assign]
        return worker

    def test_flush_returns_true_when_no_state_file(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            worker = self._make_worker(Path(td) / "worker_state.json", [], [])
            self.assertTrue(WorkerDispatcher._flush_pending_done_report(worker))

    def test_flush_blocks_claims_for_active_claim_record_without_pending_report(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            save_worker_state(path, job_id="job-1", source_path=r"C:\Media\movie.mkv")
            posts: list[tuple[str, dict]] = []
            worker = self._make_worker(path, posts, [])

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                self.assertFalse(WorkerDispatcher._flush_pending_done_report(worker))

            self.assertEqual(posts, [])
            self.assertTrue(path.exists())
            self.assertIn("unresolved active job job-1", "\n".join(logs.output))

    def test_flush_delivers_pending_report_and_clears_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            save_worker_state(
                path,
                job_id="job-1",
                source_path=r"C:\Media\movie.mkv",
                pending_done_report={"job_id": "job-1", "success": True},
            )
            posts: list[tuple[str, dict]] = []
            events: list[dict] = []
            worker = self._make_worker(path, posts, events)

            self.assertTrue(WorkerDispatcher._flush_pending_done_report(worker))

            self.assertEqual(posts[0][0], "/api/done")
            self.assertEqual(posts[0][1]["job_id"], "job-1")
            self.assertEqual(posts[0][1]["worker_id"], "worker-1")
            self.assertFalse(path.exists())
            self.assertEqual(events[0]["event"], "pending_done_recovered")

    def test_save_pending_done_report_queues_report_and_clears_active_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            save_worker_state(path, job_id="job-1", source_path=r"C:\Media\movie.mkv")
            worker = self._make_worker(path, [], [])
            job = SimpleNamespace(job_id="job-1", record=SimpleNamespace(source_path=r"C:\Media\movie.mkv"))
            payload = {"job_id": "job-1", "worker_id": "worker-1", "success": True}

            self.assertTrue(WorkerDispatcher._save_pending_done_report(worker, job, payload))  # type: ignore[arg-type]

            self.assertFalse(path.exists())
            queued = iter_pending_done_report_files(path)
            self.assertEqual(len(queued), 1)
            queued_payload = load_pending_done_report(queued[0])
            self.assertEqual(queued_payload["job_id"], "job-1")
            self.assertEqual(queued_payload["source_path"], r"C:\Media\movie.mkv")
            self.assertEqual(queued_payload["schema_version"], "worker_pending_done_report.v1")
            self.assertTrue(queued_payload["queued_utc"])

    def test_flush_delivers_queued_reports_and_strips_queue_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            queue_pending_done_report(
                path,
                job_id="job-1",
                source_path=r"C:\Media\movie.mkv",
                pending_done_report={"job_id": "job-1", "worker_id": "worker-1", "success": True},
            )
            posts: list[tuple[str, dict]] = []
            events: list[dict] = []
            worker = self._make_worker(path, posts, events)

            self.assertTrue(WorkerDispatcher._flush_pending_done_report(worker))

            self.assertEqual(len(posts), 1)
            self.assertEqual(posts[0][0], "/api/done")
            self.assertEqual(posts[0][1]["job_id"], "job-1")
            self.assertNotIn("schema_version", posts[0][1])
            self.assertNotIn("queued_utc", posts[0][1])
            self.assertEqual(iter_pending_done_report_files(path), [])
            self.assertEqual(events[0]["event"], "pending_done_recovered")

    def test_flush_holds_claims_while_delivery_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            save_worker_state(
                path,
                job_id="job-1",
                source_path=r"C:\Media\movie.mkv",
                pending_done_report={"job_id": "job-1", "success": True},
            )
            worker = self._make_worker(
                path, [], [], post_error=RuntimeError("HTTP 503 from http://x/api/done: busy"),
            )

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                self.assertFalse(WorkerDispatcher._flush_pending_done_report(worker))

            self.assertTrue(path.exists())
            self.assertIn("holding new claims", "\n".join(logs.output))

    def test_flush_quarantines_legacy_pending_report_unknown_to_coordinator(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            save_worker_state(
                path,
                job_id="job-1",
                source_path=r"C:\Media\movie.mkv",
                pending_done_report={"job_id": "job-1", "success": True},
            )
            worker = self._make_worker(
                path, [], [], post_error=RuntimeError("HTTP 404 from http://x/api/done: not found"),
            )

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                self.assertTrue(WorkerDispatcher._flush_pending_done_report(worker))

            self.assertFalse(path.exists())
            review_files = list(pending_done_reports_review_dir(path).glob("*.json"))
            self.assertEqual(len(review_files), 1)
            self.assertIn("quarantined for review and continuing claims", "\n".join(logs.output))

    def test_flush_quarantines_queued_pending_report_unknown_to_coordinator(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            queue_pending_done_report(
                path,
                job_id="job-1",
                source_path=r"C:\Media\movie.mkv",
                pending_done_report={"job_id": "job-1", "worker_id": "worker-1", "success": True},
            )
            worker = self._make_worker(
                path, [], [], post_error=RuntimeError("HTTP 404 from http://x/api/done: not found"),
            )

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                self.assertTrue(WorkerDispatcher._flush_pending_done_report(worker))

            self.assertEqual(iter_pending_done_report_files(path), [])
            review_files = list(pending_done_reports_review_dir(path).glob("*.json"))
            self.assertEqual(len(review_files), 1)
            self.assertIn("unknown to coordinator; quarantined for review and continuing claims", "\n".join(logs.output))

    def test_flush_clears_pending_report_after_late_recorded_response(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            save_worker_state(
                path,
                job_id="job-1",
                source_path=r"C:\Media\movie.mkv",
                pending_done_report={"job_id": "job-1", "success": True},
            )
            posts: list[tuple[str, dict]] = []
            events: list[dict] = []
            worker = self._make_worker(path, posts, events)
            worker._http_post = lambda post_path, payload: posts.append((post_path, payload)) or {"status": "late_recorded"}  # type: ignore[method-assign]

            self.assertTrue(WorkerDispatcher._flush_pending_done_report(worker))

            self.assertFalse(path.exists())
            self.assertEqual(events[0]["event"], "pending_done_recovered")

    def test_poll_loop_does_not_claim_with_unresolved_active_state(self) -> None:
        class StopAfterWait:
            def __init__(self) -> None:
                self.stopped = False

            def is_set(self) -> bool:
                return self.stopped

        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            save_worker_state(path, job_id="job-1", source_path=r"C:\Media\movie.mkv")
            stop = StopAfterWait()
            statuses: list[str] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = path
            worker._worker_id = "worker-1"
            worker._poll_interval = 1.0
            worker._poll_stop = stop
            worker._active_job_lock = threading.Lock()
            worker._active_job = None
            worker._notify_status = statuses.append  # type: ignore[method-assign]
            worker._http_get = lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("claim called"))  # type: ignore[method-assign]
            worker._wait_interruptible = lambda *_args, **_kwargs: setattr(stop, "stopped", True)  # type: ignore[method-assign]

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING"):
                WorkerDispatcher._poll_loop(worker)

        self.assertEqual(len(statuses), 1)
        self.assertIn("crash recovery unresolved", statuses[0])
