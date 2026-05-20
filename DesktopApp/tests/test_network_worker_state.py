from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.network.worker_state import atomic_write_text, load_worker_state, save_worker_state
from mediapipeline_desktop_app.network.worker import WorkerDispatcher, _atomic_write_text


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
            patch("mediapipeline_desktop_app.network.worker.save_worker_state", side_effect=OSError("disk full")),
            self.assertLogs("mediapipeline_desktop_app.network.worker", level="WARNING") as logs,
        ):
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
            patch("mediapipeline_desktop_app.network.worker.save_worker_state", side_effect=OSError("disk full")),
            self.assertLogs("mediapipeline_desktop_app.network.worker", level="WARNING") as logs,
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
                patch("mediapipeline_desktop_app.network.worker_state.os.replace", side_effect=OSError("replace denied")),
                patch("pathlib.Path.unlink", side_effect=OSError("cleanup denied")),
                self.assertLogs("mediapipeline_desktop_app.network.worker_state", level="WARNING") as logs,
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
            patch("mediapipeline_desktop_app.network.worker.clear_worker_state", side_effect=OSError("unlink denied")),
            self.assertLogs("mediapipeline_desktop_app.network.worker", level="WARNING") as logs,
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
            patch("mediapipeline_desktop_app.network.worker.clear_worker_state", side_effect=OSError("unlink denied")),
            self.assertLogs("mediapipeline_desktop_app.network.worker", level="WARNING") as logs,
        ):
            WorkerDispatcher._clear_worker_state_after_accepted_report(worker, "job-1", "done")

        combined = "\n".join(logs.output)
        self.assertIn("Failed to clear worker_state.json after coordinator state transition", combined)
        self.assertIn("Coordinator accepted done report for job job-1", combined)
        self.assertIn("not saving a pending done report", combined)
