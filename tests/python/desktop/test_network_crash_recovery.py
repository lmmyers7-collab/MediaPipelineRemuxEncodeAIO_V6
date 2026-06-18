from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.network.worker_state import load_worker_state
from mediapipeline.desktop.network.worker import WorkerDispatcher


class NetworkCrashRecoveryTests(unittest.TestCase):
    def test_crash_recover_keeps_state_when_done_post_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            path.write_text(
                json.dumps({"job_id": "job-1", "source_path": r"C:\Media\movie.mkv"}),
                encoding="utf-8",
            )
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = path
            worker._worker_id = "worker-1"
            worker._http_post = lambda _path, _data: (_ for _ in ()).throw(RuntimeError("offline"))
            worker.log_cluster_event = lambda **_kwargs: self.fail("cluster log should not run")

            WorkerDispatcher._crash_recover(worker)

            self.assertTrue(path.exists())

    def test_crash_recover_clears_state_after_done_post_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            path.write_text(
                json.dumps({"job_id": "job-1", "source_path": r"C:\Media\movie.mkv"}),
                encoding="utf-8",
            )
            posts: list[tuple[str, dict]] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = path
            worker._worker_id = "worker-1"
            worker._http_post = lambda post_path, data: posts.append((post_path, data)) or {}
            worker.log_cluster_event = lambda **_kwargs: None
            worker._clear_worker_state = lambda: path.unlink(missing_ok=True)

            WorkerDispatcher._crash_recover(worker)

            self.assertFalse(path.exists())
            self.assertEqual(posts[0][0], "/api/done")
            self.assertFalse(posts[0][1]["success"])

    def test_crash_recover_cleanup_failure_after_accepted_report_does_not_raise(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            path.write_text(
                json.dumps({"job_id": "job-1", "source_path": r"C:\Media\movie.mkv"}),
                encoding="utf-8",
            )
            posts: list[tuple[str, dict]] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = path
            worker._worker_id = "worker-1"
            worker._http_post = lambda post_path, data: posts.append((post_path, data)) or {}
            worker.log_cluster_event = lambda **_kwargs: None
            worker._clear_worker_state = lambda: (_ for _ in ()).throw(RuntimeError("cleanup offline"))  # type: ignore[method-assign]

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                WorkerDispatcher._crash_recover(worker)

            self.assertEqual(posts[0][0], "/api/done")
            text = "\n".join(logs.output)
            self.assertIn("Coordinator accepted crash recovery done report for job job-1", text)
            self.assertIn("not saving a pending done report", text)

    def test_crash_recover_clears_state_when_cluster_log_event_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            path.write_text(
                json.dumps({"job_id": "job-1", "source_path": r"C:\Media\movie.mkv"}),
                encoding="utf-8",
            )
            posts: list[tuple[str, dict]] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = path
            worker._worker_id = "worker-1"
            worker._http_post = lambda post_path, data: posts.append((post_path, data)) or {}
            worker.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster log blocked"))
            worker._clear_worker_state = lambda: path.unlink(missing_ok=True)

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                WorkerDispatcher._crash_recover(worker)

            self.assertFalse(path.exists())
            self.assertEqual(posts[0][0], "/api/done")
            self.assertIn("Failed to emit crash-recovered cluster event for job job-1: cluster log blocked", "\n".join(logs.output))

    def test_crash_recover_retries_pending_done_report_before_crash_failed_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            pending = {
                "job_id": "job-1",
                "worker_id": "worker-1",
                "success": True,
                "completion_status": "processed",
                "publish_state": "published",
            }
            path.write_text(
                json.dumps(
                    {
                        "job_id": "job-1",
                        "source_path": r"C:\Media\movie.mkv",
                        "pending_done_report": pending,
                    }
                ),
                encoding="utf-8",
            )
            posts: list[tuple[str, dict]] = []
            events: list[dict] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = path
            worker._worker_id = "worker-1"
            worker._http_post = lambda post_path, data: posts.append((post_path, data)) or {}
            worker.log_cluster_event = lambda **kwargs: events.append(kwargs)
            worker._clear_worker_state = lambda: path.unlink(missing_ok=True)

            WorkerDispatcher._crash_recover(worker)

            self.assertEqual(posts, [("/api/done", pending)])
            self.assertEqual(events[0]["event"], "pending_done_recovered")
            self.assertFalse(path.exists())

    def test_crash_recover_pending_done_clears_state_when_cluster_log_event_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            pending = {
                "job_id": "job-1",
                "worker_id": "worker-1",
                "success": True,
            }
            path.write_text(
                json.dumps(
                    {
                        "job_id": "job-1",
                        "source_path": r"C:\Media\movie.mkv",
                        "pending_done_report": pending,
                    }
                ),
                encoding="utf-8",
            )
            posts: list[tuple[str, dict]] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = path
            worker._worker_id = "worker-1"
            worker._http_post = lambda post_path, data: posts.append((post_path, data)) or {}
            worker.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster log blocked"))
            worker._clear_worker_state = lambda: path.unlink(missing_ok=True)

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                WorkerDispatcher._crash_recover(worker)

            self.assertFalse(path.exists())
            self.assertEqual(posts, [("/api/done", pending)])
            self.assertIn(
                "Failed to emit pending-done-recovered cluster event for job job-1: cluster log blocked",
                "\n".join(logs.output),
            )

    def test_crash_recover_pending_done_cleanup_failure_after_accepted_report_does_not_raise(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            pending = {"job_id": "job-1", "worker_id": "worker-1", "success": True}
            path.write_text(
                json.dumps(
                    {
                        "job_id": "job-1",
                        "source_path": r"C:\Media\movie.mkv",
                        "pending_done_report": pending,
                    }
                ),
                encoding="utf-8",
            )
            posts: list[tuple[str, dict]] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = path
            worker._worker_id = "worker-1"
            worker._http_post = lambda post_path, data: posts.append((post_path, data)) or {}
            worker.log_cluster_event = lambda **_kwargs: None
            worker._clear_worker_state = lambda: (_ for _ in ()).throw(RuntimeError("cleanup offline"))  # type: ignore[method-assign]

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                WorkerDispatcher._crash_recover(worker)

            self.assertEqual(posts, [("/api/done", pending)])
            text = "\n".join(logs.output)
            self.assertIn("Coordinator accepted pending done recovery report for job job-1", text)
            self.assertIn("not saving a pending done report", text)

    def test_crash_recover_keeps_pending_done_report_when_retry_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            pending = {"job_id": "job-1", "worker_id": "worker-1", "success": True}
            path.write_text(
                json.dumps(
                    {
                        "job_id": "job-1",
                        "source_path": r"C:\Media\movie.mkv",
                        "pending_done_report": pending,
                    }
                ),
                encoding="utf-8",
            )
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = path
            worker._worker_id = "worker-1"
            worker._http_post = lambda _post_path, _data: (_ for _ in ()).throw(RuntimeError("offline"))
            worker.log_cluster_event = lambda **_kwargs: self.fail("cluster log should not run")

            WorkerDispatcher._crash_recover(worker)

            self.assertTrue(path.exists())
            self.assertEqual(load_worker_state(path)["pending_done_report"], pending)

    def test_crash_recover_done_post_failure_diagnostics_are_bounded(self) -> None:
        long_error = "coordinator offline " + ("x" * 500) + "tail-marker"
        cases = (
            (
                "pending retry",
                {
                    "job_id": "job-1",
                    "source_path": r"C:\Media\movie.mkv",
                    "pending_done_report": {"job_id": "job-1", "worker_id": "worker-1", "success": True},
                },
                "Crash recovery pending done-report failed",
            ),
            (
                "crash failed",
                {"job_id": "job-1", "source_path": r"C:\Media\movie.mkv"},
                "Crash recovery done-report failed",
            ),
        )

        for name, state, expected in cases:
            with self.subTest(name=name), tempfile.TemporaryDirectory() as td:
                path = Path(td) / "worker_state.json"
                path.write_text(json.dumps(state), encoding="utf-8")
                worker = WorkerDispatcher.__new__(WorkerDispatcher)
                worker._state_path = path
                worker._worker_id = "worker-1"
                worker._http_post = lambda _post_path, _data: (_ for _ in ()).throw(RuntimeError(long_error))
                worker.log_cluster_event = lambda **_kwargs: self.fail("cluster log should not run")

                with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                    WorkerDispatcher._crash_recover(worker)

                output = "\n".join(logs.output)
                self.assertIn(expected, output)
                self.assertIn("...<truncated>", output)
                self.assertNotIn("tail-marker", output)
                self.assertTrue(path.exists())
                self.assertEqual(load_worker_state(path)["job_id"], "job-1")

    def test_crash_recover_preserves_unreadable_state_and_does_not_post_done(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            path.write_text("{not-json", encoding="utf-8")
            clears: list[bool] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = path
            worker._worker_id = "worker-1"
            worker._http_post = lambda _path, _data: self.fail("done report should not run")
            worker.log_cluster_event = lambda **_kwargs: self.fail("cluster log should not run")
            worker._clear_worker_state = lambda: clears.append(True)

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                WorkerDispatcher._crash_recover(worker)

            self.assertEqual(clears, [])
            self.assertTrue(path.exists())
            self.assertEqual(path.read_text(encoding="utf-8"), "{not-json")
            self.assertIn("Expecting property name", worker._worker_state_startup_error)
            self.assertIn("worker_state.json unreadable", "\n".join(logs.output))
            self.assertIn("preserving and holding new claims", "\n".join(logs.output))

    def test_crash_recover_logs_malformed_pending_done_before_crash_failed_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            path.write_text(
                json.dumps(
                    {
                        "job_id": "job-1",
                        "source_path": r"C:\Media\movie.mkv",
                        "pending_done_report": {"success": True},
                    }
                ),
                encoding="utf-8",
            )
            posts: list[tuple[str, dict]] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = path
            worker._worker_id = "worker-1"
            worker._http_post = lambda post_path, data: posts.append((post_path, data)) or {}
            worker.log_cluster_event = lambda **_kwargs: None
            worker._clear_worker_state = lambda: path.unlink(missing_ok=True)

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                WorkerDispatcher._crash_recover(worker)

            self.assertEqual(posts[0][0], "/api/done")
            self.assertFalse(posts[0][1]["success"])
            text = "\n".join(logs.output)
            self.assertIn("Ignoring malformed pending done report in worker_state.json for job_id=job-1", text)
            self.assertIn("Crash recovery: reporting job_id=job-1 as failed to coordinator.", text)

    def test_crash_recover_uses_guarded_clear_for_missing_job_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "worker_state.json"
            path.write_text(json.dumps({"source_path": r"C:\Media\movie.mkv"}), encoding="utf-8")
            clears: list[bool] = []
            worker = WorkerDispatcher.__new__(WorkerDispatcher)
            worker._state_path = path
            worker._worker_id = "worker-1"
            worker._http_post = lambda _path, _data: self.fail("done report should not run")
            worker.log_cluster_event = lambda **_kwargs: self.fail("cluster log should not run")
            worker._clear_worker_state = lambda: clears.append(True)

            with self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs:
                WorkerDispatcher._crash_recover(worker)

            self.assertEqual(clears, [True])
            self.assertIn("worker_state.json missing job_id", "\n".join(logs.output))
