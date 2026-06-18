from __future__ import annotations

import sys
import tempfile
import threading
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.network.worker_state import atomic_write_text, load_worker_state, save_worker_state
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
            patch("mediapipeline.desktop.network.worker_state.save_worker_state", side_effect=OSError("disk full")),
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

            with self.assertRaisesRegex(ValueError, "non-finite JSON value is not allowed"):
                load_worker_state(path)

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

    def test_flush_holds_pending_report_unknown_to_coordinator(self) -> None:
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
                self.assertFalse(WorkerDispatcher._flush_pending_done_report(worker))

            self.assertTrue(path.exists())
            self.assertIn("holding new claims", "\n".join(logs.output))

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
