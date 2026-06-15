from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.network.coordinator import CoordinatorDispatcher
from mediapipeline.desktop.network.encode_config_snapshot import snapshot_encode_config
from mediapipeline.desktop.network.path_map import parse_source_path_map
from mediapipeline.desktop.network.protocol import DoneRequest
from mediapipeline.desktop.network.registry import InFlightRegistry


class NetworkInFlightRegistryTests(unittest.TestCase):
    def test_inflight_registry_save_survives_concurrent_saves(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "inflight_registry.json"
            registry = InFlightRegistry()
            errors: list[BaseException] = []

            def save_many() -> None:
                try:
                    for _ in range(20):
                        registry.save(path)
                except BaseException as exc:
                    errors.append(exc)

            threads = [threading.Thread(target=save_many) for _ in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join()

            self.assertEqual(errors, [])
            data = json.loads(path.read_text(encoding="utf-8"))
            self.assertIn("jobs", data)
            leftovers = [p for p in path.parent.iterdir() if p.suffix == ".tmp"]
            self.assertEqual(leftovers, [])

    def test_inflight_registry_logs_temp_cleanup_failure_after_save_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "inflight_registry.json"
            registry = InFlightRegistry()

            with (
                patch("mediapipeline.desktop.network.registry.os.replace", side_effect=OSError("replace denied")),
                patch("pathlib.Path.unlink", side_effect=OSError("cleanup denied")),
                self.assertLogs("mediapipeline.desktop.network.registry", level="WARNING") as logs,
            ):
                with self.assertRaisesRegex(OSError, "replace denied"):
                    registry.save(path)

        combined = "\n".join(logs.output)
        self.assertIn("Failed to remove temporary InFlightRegistry file", combined)
        self.assertIn("cleanup denied", combined)
        self.assertIn("Failed to save InFlightRegistry", combined)
        self.assertIn("replace denied", combined)

    def test_inflight_registry_save_failure_propagates_to_coordinator_state_transition_diagnostics(self) -> None:
        events: list[dict[str, object]] = []

        with tempfile.TemporaryDirectory() as td:
            registry = InFlightRegistry()
            registry.claim(
                job_id="job-done",
                worker_id="worker-1",
                worker_name="Worker",
                source_path=r"C:\Media\done.mkv",
                encode_config={},
            )
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._registry = registry
            dispatcher._inflight_state_path = lambda: Path(td) / "coordinator_inflight.json"  # type: ignore[assignment]
            dispatcher._app = SimpleNamespace(
                root=SimpleNamespace(after=lambda _delay, callback: callback()),
                queue_records=[],
            )
            dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]
            handler = SimpleNamespace(_send_json=lambda _payload, status=200: None)
            body = json.dumps(
                DoneRequest(job_id="job-done", worker_id="worker-1", success=False).to_dict()
            ).encode("utf-8")

            with (
                patch("mediapipeline.desktop.network.registry.os.replace", side_effect=OSError("replace denied")),
                self.assertLogs("mediapipeline.desktop.network.coordinator", level="ERROR") as logs,
                self.assertLogs("mediapipeline.desktop.network.registry", level="ERROR") as registry_logs,
            ):
                CoordinatorDispatcher._http_done(dispatcher, handler, body)  # type: ignore[arg-type]

        save_events = [event for event in events if event.get("event") == "inflight_save_failed"]
        self.assertEqual(len(save_events), 1)
        self.assertIn("after done report: replace denied", str(save_events[0]["message"]))
        self.assertEqual(save_events[0]["job_id"], "job-done")
        self.assertEqual(save_events[0]["source_path"], r"C:\Media\done.mkv")
        self.assertIn("Failed to save registry after done report", "\n".join(logs.output))
        self.assertIn("Failed to save InFlightRegistry", "\n".join(registry_logs.output))

    def test_inflight_registry_claim_sanitizes_nonfinite_estimated_size(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "inflight_registry.json"
            registry = InFlightRegistry()
            with self.assertLogs("mediapipeline.desktop.network.registry", level="WARNING") as logs:
                registry.claim(
                    job_id="job-1",
                    worker_id="worker-1",
                    worker_name="Worker",
                    source_path=r"C:\Media\movie.mkv",
                    encode_config={},
                    estimated_size_gb=float("nan"),
                )

            with registry._lock:
                self.assertEqual(registry._jobs["job-1"].estimated_size_gb, 0.0)
            registry.save(path)

            self.assertTrue(path.exists())
            self.assertIn("Invalid estimated_size_gb for claimed job", "\n".join(logs.output))

    def test_inflight_registry_persists_idle_worker_seen_before_any_claim(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "inflight_registry.json"
            registry = InFlightRegistry()

            registry.note_worker_seen(worker_id="worker-1", worker_name="Worker One")
            registry.save(path)

            restored = InFlightRegistry()
            self.assertTrue(restored.load(path))
            rows = restored.idle_workers_snapshot()

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].worker_id, "worker-1")
        self.assertEqual(rows[0].worker_name, "Worker One")
        self.assertEqual(rows[0].status, "idle")
        self.assertEqual(rows[0].files_completed, 0)
        self.assertTrue(rows[0].last_heartbeat)

    def test_inflight_registry_persists_last_failure_reason_for_worker_board(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "inflight_registry.json"
            registry = InFlightRegistry()
            registry.claim(
                job_id="job-failed",
                worker_id="worker-1",
                worker_name="Worker One",
                source_path=r"C:\Media\missing.mkv",
                encode_config={},
            )
            completed = registry.complete(
                "job-failed",
                "worker-1",
                success=False,
                reason_code="SOURCE_NOT_FOUND",
                reason=r"C:\Media\missing.mkv not found on worker",
            )
            self.assertIsNotNone(completed)
            registry.save(path)

            restored = InFlightRegistry()
            self.assertTrue(restored.load(path))
            rows = restored.idle_workers_snapshot()

        self.assertEqual(len(rows), 1)
        row = rows[0].to_dict()
        self.assertEqual(row["last_failure_reason_code"], "SOURCE_NOT_FOUND")
        self.assertEqual(row["last_failure_job_id"], "job-failed")
        self.assertEqual(row["last_failure_source_path"], r"C:\Media\missing.mkv")
        self.assertIn("not found on worker", row["last_failure_reason"])
        self.assertTrue(row["last_failure_at"])

    def test_inflight_registry_suppresses_repeated_same_reason_worker_source_failures(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "inflight_registry.json"
            registry = InFlightRegistry()
            source = r"C:\Media\loop.mkv"

            for attempt in range(1, 4):
                job_id = f"job-{attempt}"
                self.assertTrue(
                    registry.claim(
                        job_id=job_id,
                        worker_id="worker-1",
                        worker_name="Worker One",
                        source_path=source,
                        encode_config={},
                    )
                )
                registry.complete(
                    job_id,
                    "worker-1",
                    success=False,
                    reason_code="SOURCE_NOT_FOUND",
                    reason=f"{source} not found on worker",
                )
                blocked = registry.claim_blocked_by_failure(worker_id="worker-1", source_path=source, max_retries=3)
                if attempt < 3:
                    self.assertIsNone(blocked)
                else:
                    self.assertIsNotNone(blocked)
                    self.assertEqual(blocked["consecutive_count"], 3)
                    self.assertEqual(blocked["reason_code"], "SOURCE_NOT_FOUND")

            alert = registry.mark_failure_quarantine_alerted(worker_id="worker-1", source_path=source, max_retries=3)
            duplicate_alert = registry.mark_failure_quarantine_alerted(worker_id="worker-1", source_path=source, max_retries=3)
            registry.save(path)

            restored = InFlightRegistry()
            self.assertTrue(restored.load(path))
            restored_blocked = restored.claim_blocked_by_failure(worker_id="worker-1", source_path=source, max_retries=3)
            rows = [row.to_dict() for row in restored.idle_workers_snapshot()]

        self.assertIsNotNone(alert)
        self.assertIsNone(duplicate_alert)
        self.assertIsNotNone(restored_blocked)
        self.assertEqual(restored_blocked["consecutive_count"], 3)
        self.assertEqual(rows[0]["worker_misconfigured_reason_code"], "SOURCE_NOT_FOUND")
        self.assertEqual(rows[0]["failure_streak_count"], 3)

    def test_network_config_json_fields_reject_nonfinite_constants(self) -> None:
        with self.assertLogs("mediapipeline.desktop.network.path_map", level="WARNING") as path_logs:
            self.assertEqual(parse_source_path_map('{"C:/Media": NaN}'), [])
        self.assertIn("non-finite JSON value is not allowed", "\n".join(path_logs.output))

        config = {
            "VideoCodec": "copy",
            "WorkerConfigOverrides": '{"worker": {"VideoQuality": NaN}}',
        }
        with self.assertLogs("mediapipeline.desktop.network.encode_config_snapshot", level="WARNING") as encode_logs:
            self.assertEqual(snapshot_encode_config(config, "worker"), {"VideoCodec": "copy"})
        self.assertIn("WorkerConfigOverrides is disabled by backend policy", "\n".join(encode_logs.output))

    def test_inflight_registry_load_skips_malformed_rows_without_partial_failure(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "inflight_registry.json"
            valid_source = r"C:\Media\valid.mkv"
            path.write_text(
                json.dumps(
                    {
                        "jobs": [
                            {
                                "job_id": "job-1",
                                "worker_id": "worker-1",
                                "worker_name": "Worker 1",
                                "source_path": valid_source,
                                "claimed_at": "2026-05-08T00:00:00+00:00",
                                "last_heartbeat": "2026-05-08T00:01:00+00:00",
                                "progress_percent": 42,
                                "current_stage": "encoding",
                                "encode_config": {},
                                "priority": True,
                                "estimated_size_gb": 1.5,
                            },
                            {
                                "job_id": "bad-progress",
                                "worker_id": "worker-2",
                                "worker_name": "Worker 2",
                                "source_path": r"C:\Media\bad.mkv",
                                "claimed_at": "2026-05-08T00:00:00+00:00",
                                "last_heartbeat": "2026-05-08T00:01:00+00:00",
                                "progress_percent": "not-a-number",
                            },
                            {
                                "job_id": "bad-size",
                                "worker_id": "worker-3",
                                "worker_name": "Worker 3",
                                "source_path": r"C:\Media\bad-size.mkv",
                                "claimed_at": "2026-05-08T00:00:00+00:00",
                                "last_heartbeat": "2026-05-08T00:01:00+00:00",
                                "estimated_size_gb": "NaN",
                            },
                            ["not", "an", "object"],
                            {"job_id": "", "source_path": r"C:\Media\missing-id.mkv"},
                        ],
                        "session_completed": "bad-counter",
                        "session_failed": "2",
                        "worker_stats": {
                            "worker-1": {"name": "Worker 1", "files": "3", "gb": "6.5", "secs": "120"},
                            "worker-bad": {"files": "not-a-number"},
                            "worker-bad-gb": {"files": "1", "gb": "NaN", "secs": "120"},
                        },
                    }
                ),
                encoding="utf-8",
            )
            registry = InFlightRegistry()

            with self.assertLogs("mediapipeline.desktop.network.registry", level="WARNING") as logs:
                registry.load(path)

            self.assertTrue(registry.is_in_flight(valid_source))
            snapshot = registry.snapshot()
            self.assertEqual(len(snapshot), 1)
            self.assertEqual(snapshot[0].worker_id, "worker-1")
            self.assertEqual(snapshot[0].files_completed, 3)
            self.assertEqual(registry.session_completed, 0)
            self.assertEqual(registry.session_failed, 2)
            text = "\n".join(logs.output)
            self.assertIn("Skipping malformed in-flight job", text)
            self.assertIn("Skipping incomplete in-flight job", text)
            self.assertIn("Invalid session_completed", text)
            self.assertIn("Skipping malformed worker stats", text)
