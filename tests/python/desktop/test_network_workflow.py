from __future__ import annotations

import json
import sys
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.network.cluster_log import format_cluster_log_line
from mediapipeline.desktop.network import get_dispatcher
from mediapipeline.desktop.network.coordinator import CoordinatorDispatcher, _CoordHandler
from mediapipeline.desktop.network.coordinator_policy import compute_retry_after_seconds
from mediapipeline.desktop.network.protocol import ClaimResponse, DoneRequest, LogEntryRequest
from mediapipeline.desktop.network.registry import InFlightRegistry
from mediapipeline.desktop.network.standalone import StandaloneDispatcher
from mediapipeline.desktop.network.poll_policy import resolve_worker_wait_seconds
from mediapipeline.desktop.network.worker import WorkerDispatcher


class WorkflowEnhancementTests(unittest.TestCase):
    """Coverage for the W1/W2/W3/W5/W6/W7 workflow improvements."""

    def _inflight_state_job(self, *, job_id: str, source_path: str, worker_id: str = "worker-1") -> dict[str, object]:
        return {
            "job_id": job_id,
            "worker_id": worker_id,
            "worker_name": worker_id,
            "source_path": source_path,
            "claimed_at": "2026-05-08T12:00:00+00:00",
            "last_heartbeat": "2026-05-08T12:00:00+00:00",
            "progress_percent": 0.0,
            "current_stage": "encode",
            "encode_config": {},
            "priority": False,
            "estimated_size_gb": 0.0,
        }

    # ------------------------------------------------------------------
    # W1 — mark_done() forwards parameters into _emit_done_outcome
    # ------------------------------------------------------------------
    def test_local_claim_is_denied_when_inflight_save_fails(self) -> None:
        reg = InFlightRegistry()

        def _save_denied(_path: Path) -> None:
            raise RuntimeError("save denied")

        reg.save = _save_denied  # type: ignore[method-assign]
        record = SimpleNamespace(source_path=r"C:\Media\movie.mkv", priority=True)
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._registry = reg
        dispatcher._claim_lock = threading.Lock()
        dispatcher._app = SimpleNamespace(_machine_id="coord-pc")
        dispatcher._config = lambda: {"CoordinatorAlsoEncodeLocally": True}  # type: ignore[assignment]
        dispatcher._scan_for_next_record = lambda _worker_name: (record, {"Codec": "copy"})  # type: ignore[assignment]
        dispatcher._inflight_state_path = lambda: Path(tempfile.gettempdir()) / "ignored.json"  # type: ignore[assignment]
        events: list[dict] = []
        dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            job = CoordinatorDispatcher.claim_next(dispatcher)

        self.assertIsNone(job)
        self.assertFalse(reg.is_in_flight(r"C:\Media\movie.mkv"))
        self.assertIn("Failed to save inflight state after local claim", "\n".join(logs.output))
        self.assertEqual(events[0]["event"], "inflight_save_failed")
        self.assertIn("Local claim denied because in-flight registry could not be saved: save denied", events[0]["message"])
        self.assertEqual(events[0]["source_path"], r"C:\Media\movie.mkv")

    def test_inflight_registry_load_rejects_duplicate_job_id(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "coordinator_inflight.json"
            state_path.write_text(
                json.dumps(
                    {
                        "jobs": [
                            self._inflight_state_job(job_id="job-1", source_path=r"C:\Media\first.mkv"),
                            self._inflight_state_job(job_id="job-1", source_path=r"C:\Media\second.mkv", worker_id="worker-2"),
                        ]
                    }
                ),
                encoding="utf-8",
            )
            registry = InFlightRegistry()
            self.assertTrue(
                registry.claim(
                    job_id="existing",
                    worker_id="worker-existing",
                    worker_name="worker-existing",
                    source_path=r"C:\Media\existing.mkv",
                    encode_config={},
                )
            )

            with self.assertLogs("mediapipeline.desktop.network.registry", level="ERROR") as logs:
                loaded = registry.load(state_path)

        self.assertFalse(loaded)
        self.assertEqual(registry.active_count, 1)
        self.assertTrue(registry.is_in_flight(r"C:\Media\existing.mkv"))
        self.assertFalse(registry.is_in_flight(r"C:\Media\first.mkv"))
        self.assertIn("duplicate in-flight job_id", "\n".join(logs.output))

    def test_inflight_registry_load_rejects_duplicate_source_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "coordinator_inflight.json"
            state_path.write_text(
                json.dumps(
                    {
                        "jobs": [
                            self._inflight_state_job(job_id="job-1", source_path=r"C:\Media\same.mkv"),
                            self._inflight_state_job(job_id="job-2", source_path=r"C:\Media\same.mkv", worker_id="worker-2"),
                        ]
                    }
                ),
                encoding="utf-8",
            )
            registry = InFlightRegistry()

            with self.assertLogs("mediapipeline.desktop.network.registry", level="ERROR") as logs:
                loaded = registry.load(state_path)

        self.assertFalse(loaded)
        self.assertEqual(registry.active_count, 0)
        self.assertFalse(registry.is_in_flight(r"C:\Media\same.mkv"))
        self.assertIn("duplicate in-flight source_path", "\n".join(logs.output))

    def test_local_release_survives_inflight_save_failure(self) -> None:
        reg = InFlightRegistry()
        reg.claim(
            job_id="local-1",
            worker_id="coord-pc",
            worker_name="coordinator",
            source_path=r"C:\Media\movie.mkv",
            encode_config={},
        )

        def _save_denied(_path: Path) -> None:
            raise RuntimeError("save denied")

        reg.save = _save_denied  # type: ignore[method-assign]
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._registry = reg
        dispatcher._inflight_state_path = lambda: Path(tempfile.gettempdir()) / "ignored.json"  # type: ignore[assignment]
        events: list[dict] = []
        dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]
        job = SimpleNamespace(job_id="local-1", worker_id="coord-pc")

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher.release(dispatcher, job)

        self.assertEqual(reg.active_count, 0)
        self.assertIn("Failed to save inflight state after local release local-1", "\n".join(logs.output))
        self.assertEqual(events[0]["event"], "inflight_save_failed")
        self.assertIn("after local release: save denied", events[0]["message"])
        self.assertEqual(events[0]["job_id"], "local-1")

    def test_local_heartbeat_survives_malformed_progress(self) -> None:
        reg = InFlightRegistry()
        reg.claim(
            job_id="local-1",
            worker_id="coord-pc",
            worker_name="coordinator",
            source_path=r"C:\Media\movie.mkv",
            encode_config={},
        )
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._registry = reg
        job = SimpleNamespace(job_id="local-1", worker_id="coord-pc")

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            keep_alive = CoordinatorDispatcher.heartbeat(
                dispatcher,
                job,
                progress=float("nan"),
                stage="encoding",
            )

        self.assertTrue(keep_alive)
        self.assertEqual(reg.active_count, 1)
        self.assertIn("Local coordinator heartbeat failed for job local-1; keeping job active", "\n".join(logs.output))

    def test_mark_done_forwards_parameters_into_cluster_log(self) -> None:
        """Local-encode mark_done() must produce the same cluster.log
        entries as the HTTP /api/done handler — previously they were
        silently dropped."""
        reg = InFlightRegistry()
        reg.claim(
            job_id="local-1", worker_id="coord-pc", worker_name="coordinator",
            source_path=r"\\share\movie.mkv", encode_config={},
        )

        events: list[dict] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._registry = reg
        dispatcher._app = SimpleNamespace(
            root=SimpleNamespace(after=lambda _delay, _fn=None: None),
            queue_records=[],
        )
        dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]
        # Stub registry.save and queue removal — we only care about the log.
        dispatcher._inflight_state_path = lambda: Path(tempfile.gettempdir()) / "ignored.json"
        dispatcher._remove_from_queue = lambda _sp: None  # type: ignore[assignment]

        job = SimpleNamespace(job_id="local-1", worker_id="coord-pc")
        CoordinatorDispatcher.mark_done(
            dispatcher,
            job,
            success=True,
            elapsed_seconds=12.5,
            output_size_bytes=4 * 1024 * 1024,
            completion_status="processed",
            publish_state="pending",
            publish_mode="parked",
        )
        # An entry must have been emitted, and it must reflect the
        # publish_state we passed (the previous mark_done dropped it).
        self.assertTrue(events, "mark_done must emit a cluster_log event for local encodes")
        self.assertEqual(events[0]["event"], "job_completed_pending_publish")
        self.assertIn("pending/parked", events[0]["message"])

    def test_local_completion_save_failure_restores_target_and_preserves_concurrent_state(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "coordinator_inflight.json"
            registry = InFlightRegistry()
            for job_id, worker_id, source_path in (
                ("job-target", "coord-pc", r"C:\Media\target.mkv"),
                ("job-other", "worker-other", r"C:\Media\other.mkv"),
            ):
                self.assertTrue(
                    registry.claim(
                        job_id=job_id,
                        worker_id=worker_id,
                        worker_name=worker_id,
                        source_path=source_path,
                        encode_config={},
                    )
                )
            registry.save(state_path)
            original_save = registry.save
            save_calls = 0

            def fail_first_save(path: Path) -> None:
                nonlocal save_calls
                save_calls += 1
                if save_calls == 1:
                    self.assertIsNotNone(
                        registry.complete("job-other", "worker-other", success=True)
                    )
                    self.assertTrue(
                        registry.claim(
                            job_id="job-new",
                            worker_id="worker-new",
                            worker_name="worker-new",
                            source_path=r"C:\Media\new.mkv",
                            encode_config={},
                        )
                    )
                    raise OSError("injected local completion save failure")
                original_save(path)

            registry.save = fail_first_save  # type: ignore[method-assign]
            scheduled: list[object] = []
            events: list[dict[str, object]] = []
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._registry = registry
            dispatcher._app = SimpleNamespace(
                root=SimpleNamespace(after=lambda _delay, callback: scheduled.append(callback)),
                queue_records=[SimpleNamespace(source_path=r"C:\Media\target.mkv")],
            )
            dispatcher._config = lambda: {}  # type: ignore[assignment]
            dispatcher._inflight_state_path = lambda: state_path  # type: ignore[assignment]
            dispatcher._remove_from_queue = lambda _source_path: None  # type: ignore[assignment]
            dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]
            job = SimpleNamespace(
                job_id="job-target",
                worker_id="coord-pc",
                record=SimpleNamespace(source_path=r"C:\Media\target.mkv"),
            )

            with self.assertRaisesRegex(RuntimeError, "registry save failed after done report"):
                CoordinatorDispatcher.mark_done(dispatcher, job, success=True)

            self.assertEqual(scheduled, [])
            self.assertEqual(save_calls, 2)
            with registry._lock:
                self.assertEqual(set(registry._jobs), {"job-target", "job-new"})
                self.assertEqual(registry.session_completed, 1)

            restored = InFlightRegistry()
            self.assertTrue(restored.load(state_path))
            with restored._lock:
                self.assertEqual(set(restored._jobs), {"job-target", "job-new"})
                self.assertEqual(restored.session_completed, 1)

    def test_local_network_rerun_save_failure_restores_claim_before_row_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "coordinator_inflight.json"
            registry = InFlightRegistry()
            self.assertTrue(
                registry.claim(
                    job_id="job-rerun",
                    worker_id="coord-pc",
                    worker_name="coordinator",
                    source_path=r"C:\Media\rerun.mkv",
                    encode_config={},
                    job_kind="csv_rerun_row",
                    claim_metadata={
                        "job_kind": "csv_rerun_row",
                        "rerun_batch_id": "batch-1",
                        "rerun_row_key": "row-1",
                    },
                )
            )
            registry.save(state_path)
            original_save = registry.save
            save_calls = 0

            def fail_first_save(path: Path) -> None:
                nonlocal save_calls
                save_calls += 1
                if save_calls == 1:
                    raise OSError("injected local rerun save failure")
                original_save(path)

            registry.save = fail_first_save  # type: ignore[method-assign]
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._registry = registry
            dispatcher._app = SimpleNamespace()
            dispatcher._inflight_state_path = lambda: state_path  # type: ignore[assignment]
            dispatcher.log_cluster_event = lambda **_kwargs: None  # type: ignore[assignment]
            job = SimpleNamespace(
                job_id="job-rerun",
                worker_id="coord-pc",
                record=SimpleNamespace(source_path=r"C:\Media\rerun.mkv"),
            )

            with patch(
                "mediapipeline.desktop.network.coordinator_queue.update_network_rerun_row_done"
            ) as update_row:
                with self.assertRaisesRegex(
                    RuntimeError,
                    "registry save failed after local Network CSV rerun done",
                ):
                    CoordinatorDispatcher.mark_done(dispatcher, job, success=True)

            update_row.assert_not_called()
            self.assertEqual(save_calls, 2)
            with registry._lock:
                self.assertEqual(set(registry._jobs), {"job-rerun"})
            restored = InFlightRegistry()
            self.assertTrue(restored.load(state_path))
            with restored._lock:
                self.assertEqual(set(restored._jobs), {"job-rerun"})

    def test_local_failed_completion_save_failure_restores_failure_ledger(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "coordinator_inflight.json"
            registry = InFlightRegistry()
            self.assertTrue(
                registry.claim(
                    job_id="job-failed",
                    worker_id="coord-pc",
                    worker_name="coordinator",
                    source_path=r"C:\Media\failed.mkv",
                    encode_config={},
                )
            )
            registry.save(state_path)
            original_save = registry.save
            save_calls = 0

            def fail_first_save(path: Path) -> None:
                nonlocal save_calls
                save_calls += 1
                if save_calls == 1:
                    raise OSError("injected failed-outcome save failure")
                original_save(path)

            registry.save = fail_first_save  # type: ignore[method-assign]
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._registry = registry
            dispatcher._app = SimpleNamespace(root=SimpleNamespace(after=lambda *_args: None))
            dispatcher._config = lambda: {}  # type: ignore[assignment]
            dispatcher._inflight_state_path = lambda: state_path  # type: ignore[assignment]
            dispatcher._remove_from_queue = lambda _source_path: None  # type: ignore[assignment]
            dispatcher.log_cluster_event = lambda **_kwargs: None  # type: ignore[assignment]
            job = SimpleNamespace(
                job_id="job-failed",
                worker_id="coord-pc",
                record=SimpleNamespace(source_path=r"C:\Media\failed.mkv"),
            )

            with self.assertRaisesRegex(RuntimeError, "registry save failed after done report"):
                CoordinatorDispatcher.mark_done(
                    dispatcher,
                    job,
                    success=False,
                    error="synthetic encode failure",
                    reason_code="ENCODE_ERROR",
                )

            with registry._lock:
                self.assertEqual(set(registry._jobs), {"job-failed"})
                self.assertEqual(registry.session_failed, 0)
                self.assertEqual(registry._failure_ledger, {})
            restored = InFlightRegistry()
            self.assertTrue(restored.load(state_path))
            with restored._lock:
                self.assertEqual(set(restored._jobs), {"job-failed"})
                self.assertEqual(restored.session_failed, 0)
                self.assertEqual(restored._failure_ledger, {})

    def test_local_network_rerun_row_conflict_restores_durable_claim(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "coordinator_inflight.json"
            registry = InFlightRegistry()
            self.assertTrue(
                registry.claim(
                    job_id="job-rerun-conflict",
                    worker_id="coord-pc",
                    worker_name="coordinator",
                    source_path=r"C:\Media\rerun-conflict.mkv",
                    encode_config={},
                    job_kind="csv_rerun_row",
                    claim_metadata={"job_kind": "csv_rerun_row"},
                )
            )
            registry.save(state_path)
            save_calls = 0
            original_save = registry.save

            def count_save(path: Path) -> None:
                nonlocal save_calls
                save_calls += 1
                original_save(path)

            registry.save = count_save  # type: ignore[method-assign]
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._registry = registry
            dispatcher._app = SimpleNamespace()
            dispatcher._inflight_state_path = lambda: state_path  # type: ignore[assignment]
            dispatcher.log_cluster_event = lambda **_kwargs: None  # type: ignore[assignment]
            job = SimpleNamespace(
                job_id="job-rerun-conflict",
                worker_id="coord-pc",
                record=SimpleNamespace(source_path=r"C:\Media\rerun-conflict.mkv"),
            )

            with patch(
                "mediapipeline.desktop.network.coordinator_queue.update_network_rerun_row_done",
                return_value=False,
            ):
                with self.assertRaisesRegex(
                    RuntimeError,
                    "Network rerun row completion compare-and-set was rejected",
                ):
                    CoordinatorDispatcher.mark_done(dispatcher, job, success=True)

            self.assertEqual(save_calls, 2)
            with registry._lock:
                self.assertEqual(set(registry._jobs), {"job-rerun-conflict"})
            restored = InFlightRegistry()
            self.assertTrue(restored.load(state_path))
            with restored._lock:
                self.assertEqual(set(restored._jobs), {"job-rerun-conflict"})

    def test_http_done_failure_reason_propagates_to_registry_and_cluster_log(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            registry = InFlightRegistry()
            registry.claim(
                job_id="job-source-missing",
                worker_id="worker-1",
                worker_name="Worker",
                source_path=r"C:\Media\missing.mkv",
                encode_config={},
            )
            events: list[dict] = []
            sent: list[tuple[dict, int]] = []
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._registry = registry
            dispatcher._app = SimpleNamespace(root=SimpleNamespace(after=lambda _delay, _fn=None: None), queue_records=[])
            dispatcher._remove_from_queue = lambda _sp: None  # type: ignore[assignment]
            dispatcher._inflight_state_path = lambda: Path(td) / "coordinator_inflight.json"
            dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]
            handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))
            request = DoneRequest(
                job_id="job-source-missing",
                worker_id="worker-1",
                success=False,
                error_message=r"C:\Media\missing.mkv not found on worker",
            )

            CoordinatorDispatcher._http_done(
                dispatcher,
                handler,  # type: ignore[arg-type]
                json.dumps(request.to_dict()).encode("utf-8"),
            )

            rows = [row.to_dict() for row in registry.idle_workers_snapshot()]

        self.assertEqual(sent, [({"status": "ok"}, 200)])
        self.assertEqual(events[0]["event"], "job_failed")
        self.assertIn("reason_code=SOURCE_NOT_FOUND", events[0]["message"])
        self.assertNotIn("reason_code", events[0])
        self.assertEqual(rows[0]["last_failure_reason_code"], "SOURCE_NOT_FOUND")
        self.assertEqual(rows[0]["last_failure_job_id"], "job-source-missing")
        self.assertEqual(rows[0]["last_failure_source_path"], r"C:\Media\missing.mkv")
        self.assertIn("not found on worker", rows[0]["last_failure_reason"])

    def test_repeated_same_reason_worker_failures_stop_same_worker_redispatch(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = r"C:\Media\loop.mkv"
            record = SimpleNamespace(source_path=source, priority=False, estimated_size_gb=1.0)
            events: list[dict] = []
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._registry = InFlightRegistry()
            dispatcher._registry._RECENT_COMPLETION_TTL_SECONDS = 0.0
            dispatcher._claim_lock = threading.Lock()
            dispatcher._accepting_claims = True
            dispatcher._app = SimpleNamespace(
                root=SimpleNamespace(after=lambda _delay, _fn=None: None),
                queue_records=[record],
                failure_records=[],
            )
            dispatcher._config = lambda: {"CoordinatorMaxJobRetries": 3}  # type: ignore[assignment]
            dispatcher._remove_from_queue = lambda _sp: None  # type: ignore[assignment]
            dispatcher._inflight_state_path = lambda: Path(td) / "coordinator_inflight.json"
            dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]

            for _attempt in range(1, 4):
                claim_sent: list[tuple[dict, int]] = []
                claim_handler = SimpleNamespace(
                    _send_json=lambda payload, status=200, claim_sent=claim_sent: claim_sent.append((payload, status))
                )
                CoordinatorDispatcher._http_claim(
                    dispatcher,
                    claim_handler,  # type: ignore[arg-type]
                    {"worker_id": "worker-1", "worker_name": "Worker One"},
                )
                claim_payload = claim_sent[-1][0]
                self.assertEqual(claim_payload["status"], "ok")
                done_sent: list[tuple[dict, int]] = []
                done_handler = SimpleNamespace(
                    _send_json=lambda payload, status=200, done_sent=done_sent: done_sent.append((payload, status))
                )
                CoordinatorDispatcher._http_done(
                    dispatcher,
                    done_handler,  # type: ignore[arg-type]
                    json.dumps(
                        DoneRequest(
                            job_id=claim_payload["job_id"],
                            worker_id="worker-1",
                            success=False,
                            error_message=f"{source} not found on worker",
                        ).to_dict()
                    ).encode("utf-8"),
                )
                self.assertEqual(done_sent[-1], ({"status": "ok"}, 200))
                with dispatcher._registry._lock:
                    dispatcher._registry._recent_completions.clear()

            blocked_claim_sent: list[tuple[dict, int]] = []
            blocked_handler = SimpleNamespace(_send_json=lambda payload, status=200: blocked_claim_sent.append((payload, status)))
            CoordinatorDispatcher._http_claim(
                dispatcher,
                blocked_handler,  # type: ignore[arg-type]
                {"worker_id": "worker-1", "worker_name": "Worker One"},
            )
            rows = [row.to_dict() for row in dispatcher._registry.idle_workers_snapshot()]

        quarantine_events = [event for event in events if event.get("event") == "worker_quarantined"]
        self.assertEqual(blocked_claim_sent[-1][0]["status"], "empty")
        self.assertEqual(len(quarantine_events), 1)
        self.assertIn("Suppressed future claims", quarantine_events[0]["message"])
        self.assertIn("SOURCE_NOT_FOUND failure(s)", quarantine_events[0]["message"])
        self.assertNotIn("reason_code", quarantine_events[0])
        self.assertNotIn("consecutive_count", quarantine_events[0])
        self.assertEqual(rows[0]["worker_misconfigured_reason_code"], "SOURCE_NOT_FOUND")

    def test_http_done_failure_and_quarantine_use_production_cluster_log_signature(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app_state_path = root / "LocalBase" / "State" / "App" / "desktop_app_state.json"
            source = r"C:\Media\missing.mkv"
            registry = InFlightRegistry()
            registry.claim(
                job_id="job-prod",
                worker_id="worker-1",
                worker_name="Worker One",
                source_path=source,
                encode_config={},
            )
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._registry = registry
            dispatcher._cluster_log_lock = threading.Lock()
            dispatcher._cluster_log_max_bytes = 1024 * 1024
            dispatcher._app = SimpleNamespace(
                root=SimpleNamespace(after=lambda _delay, _fn=None: None),
                queue_records=[],
                service=SimpleNamespace(app_state_path=app_state_path),
                _machine_id="coord-1",
            )
            dispatcher._config = lambda: {"CoordinatorMaxJobRetries": 1}  # type: ignore[assignment]
            dispatcher._remove_from_queue = lambda _sp: None  # type: ignore[assignment]
            dispatcher._inflight_state_path = lambda: root / "coordinator_inflight.json"
            sent: list[tuple[dict, int]] = []
            handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))
            request = DoneRequest(
                job_id="job-prod",
                worker_id="worker-1",
                success=False,
                error_message=r"C:\Media\missing.mkv not found on worker token=done-secret",
            )

            CoordinatorDispatcher._http_done(
                dispatcher,
                handler,  # type: ignore[arg-type]
                json.dumps(request.to_dict()).encode("utf-8"),
            )

            cluster_log = app_state_path.parent / "cluster.log"
            text = cluster_log.read_text(encoding="utf-8")

        self.assertEqual(sent, [({"status": "ok"}, 200)])
        self.assertIn("job_failed", text)
        self.assertIn("worker_quarantined", text)
        self.assertIn("SOURCE_NOT_FOUND", text)
        self.assertNotIn("done-secret", text)

    def test_http_done_outcome_cluster_log_failure_does_not_block_response_or_save(self) -> None:
        class Root:
            def after(self, _delay: int, callback: object) -> None:
                callback()

        cases = (
            (
                "job-success",
                DoneRequest(job_id="job-success", worker_id="worker-1", success=True),
                "job-completed",
            ),
            (
                "job-failed",
                DoneRequest(
                    job_id="job-failed",
                    worker_id="worker-1",
                    success=False,
                    error_message="encode failed",
                    queue_terminal=True,
                ),
                "job-terminal-failed",
            ),
        )

        for job_id, request, context in cases:
            with self.subTest(context=context):
                registry = InFlightRegistry()
                source = rf"C:\Media\{job_id}.mkv"
                registry.claim(
                    job_id=job_id,
                    worker_id="worker-1",
                    worker_name="Worker",
                    source_path=source,
                    encode_config={},
                )
                saved: list[Path] = []
                registry.save = lambda path, saved=saved: saved.append(path)  # type: ignore[method-assign]
                removed: list[str] = []
                state_path = Path(tempfile.gettempdir()) / f"{job_id}.json"
                dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
                dispatcher._registry = registry
                dispatcher._app = SimpleNamespace(root=Root(), queue_records=[])
                dispatcher._remove_from_queue = lambda source_path, removed=removed: removed.append(source_path)  # type: ignore[assignment]
                dispatcher._inflight_state_path = lambda state_path=state_path: state_path
                dispatcher.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster blocked"))  # type: ignore[assignment]
                sent: list[tuple[dict, int]] = []
                handler = SimpleNamespace(_send_json=lambda payload, status=200, sent=sent: sent.append((payload, status)))

                with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
                    CoordinatorDispatcher._http_done(
                        dispatcher,
                        handler,  # type: ignore[arg-type]
                        json.dumps(request.to_dict()).encode("utf-8"),
                    )

                self.assertEqual(sent, [({"status": "ok"}, 200)])
                self.assertEqual(saved, [state_path])
                self.assertEqual(removed, [source])
                self.assertEqual(registry.active_count, 0)
                output = "\n".join(logs.output)
                self.assertIn(f"Failed to emit {context} cluster event for job {job_id[:8]}", output)
                self.assertIn("cluster blocked", output)

    def test_mark_done_handles_reclaimed_job_without_logging(self) -> None:
        """If the job was reclaimed by the reaper before mark_done lands,
        the helper must not crash and must not produce a misleading
        cluster_log entry pointing at a nonexistent job."""
        reg = InFlightRegistry()
        events: list[dict] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._registry = reg
        dispatcher._app = SimpleNamespace(root=None, queue_records=[])
        dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]
        dispatcher._inflight_state_path = lambda: Path(tempfile.gettempdir()) / "ignored.json"

        job = SimpleNamespace(job_id="ghost", worker_id="coord-pc")
        # Should not raise, should not emit a cluster log entry.
        CoordinatorDispatcher.mark_done(dispatcher, job, success=True, elapsed_seconds=0.0)
        self.assertEqual(events, [])

    def test_missing_local_completion_save_failure_emits_diagnostic_event(self) -> None:
        class SaveFailingRegistry(InFlightRegistry):
            def save(self, _path: Path) -> None:
                raise RuntimeError("save denied")

        events: list[dict] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._registry = SaveFailingRegistry()
        dispatcher._app = SimpleNamespace(root=None, queue_records=[])
        dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]
        dispatcher._inflight_state_path = lambda: Path(tempfile.gettempdir()) / "ignored.json"
        job = SimpleNamespace(
            job_id="ghost",
            worker_id="coord-pc",
            record=SimpleNamespace(source_path=r"C:\Media\ghost.mkv"),
        )

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher.mark_done(dispatcher, job, success=True, elapsed_seconds=0.0)

        self.assertEqual(events[0]["event"], "inflight_save_failed")
        self.assertIn("after missing local completion: save denied", events[0]["message"])
        self.assertEqual(events[0]["job_id"], "ghost")
        self.assertEqual(events[0]["source_path"], r"C:\Media\ghost.mkv")
        self.assertIn("Failed to save inflight state after missing local completion", "\n".join(logs.output))

    def test_terminal_done_queue_removal_schedule_failure_removes_directly(self) -> None:
        class BadRoot:
            def after(self, _delay: int, _callback: object) -> None:
                raise RuntimeError("tk offline")

        saves: list[Path] = []
        events: list[dict] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._app = SimpleNamespace(root=BadRoot(), queue_records=[])
        dispatcher._registry = SimpleNamespace(save=lambda path: saves.append(path))
        dispatcher._inflight_state_path = lambda: Path(tempfile.gettempdir()) / "ignored.json"
        dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]
        job = SimpleNamespace(job_id="job-1", source_path=r"C:\Media\movie.mkv", worker_name="Worker")

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="INFO") as logs:
            CoordinatorDispatcher._emit_done_outcome(
                dispatcher,
                job=job,
                success=False,
                worker_id="worker-1",
                elapsed_seconds=0.0,
                output_size_bytes=0,
                completion_status="failed",
                publish_state="",
                publish_mode="",
                error_message="encode failed",
                queue_terminal=True,
                retry_on_failure=True,
            )

        text = "\n".join(logs.output)
        self.assertIn("App scheduler unavailable after done report for movie.mkv", text)
        self.assertIn("queue record removed directly", text)
        self.assertIn("tk offline", text)
        self.assertEqual(len(events), 1)
        self.assertEqual(len(saves), 1)

    def test_terminal_done_queue_removal_warns_when_direct_removal_also_fails(self) -> None:
        class BadRoot:
            def after(self, _delay: int, _callback: object) -> None:
                raise RuntimeError("tk offline")

        class ExplodingRecords:
            def __bool__(self) -> bool:
                return True

            def __iter__(self):
                raise RuntimeError("records unavailable")

        saves: list[Path] = []
        events: list[dict] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._app = SimpleNamespace(root=BadRoot(), queue_records=ExplodingRecords())
        dispatcher._registry = SimpleNamespace(save=lambda path: saves.append(path))
        dispatcher._inflight_state_path = lambda: Path(tempfile.gettempdir()) / "ignored.json"
        dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]
        job = SimpleNamespace(job_id="job-1", source_path=r"C:\Media\movie.mkv", worker_name="Worker")

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher._emit_done_outcome(
                dispatcher,
                job=job,
                success=False,
                worker_id="worker-1",
                elapsed_seconds=0.0,
                output_size_bytes=0,
                completion_status="failed",
                publish_state="",
                publish_mode="",
                error_message="encode failed",
                queue_terminal=True,
                retry_on_failure=True,
            )

        text = "\n".join(logs.output)
        self.assertIn("Failed to schedule queue removal after done report for movie.mkv", text)
        self.assertIn("queue record may remain claimable until manually removed", text)
        self.assertIn("tk offline", text)
        self.assertEqual(len(events), 1)
        self.assertEqual(len(saves), 1)

    def test_terminal_done_queue_removal_success_logs_scheduled_not_removed(self) -> None:
        class GoodRoot:
            def __init__(self) -> None:
                self.calls: list[tuple[int, object]] = []

            def after(self, delay: int, callback: object) -> None:
                self.calls.append((delay, callback))

        root = GoodRoot()
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._app = SimpleNamespace(root=root, queue_records=[])
        dispatcher._registry = SimpleNamespace(save=lambda _path: None)
        dispatcher._inflight_state_path = lambda: Path(tempfile.gettempdir()) / "ignored.json"
        dispatcher.log_cluster_event = lambda **_kwargs: None  # type: ignore[assignment]
        job = SimpleNamespace(job_id="job-1", source_path=r"C:\Media\movie.mkv", worker_name="Worker")

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="INFO") as logs:
            CoordinatorDispatcher._emit_done_outcome(
                dispatcher,
                job=job,
                success=False,
                worker_id="worker-1",
                elapsed_seconds=0.0,
                output_size_bytes=0,
                completion_status="failed",
                publish_state="",
                publish_mode="",
                error_message="encode failed",
                queue_terminal=True,
                retry_on_failure=True,
            )

        text = "\n".join(logs.output)
        self.assertIn("Retry policy: scheduled queue removal for movie.mkv", text)
        self.assertNotIn("Retry policy: removed movie.mkv from queue", text)
        self.assertEqual(len(root.calls), 1)
        self.assertEqual(root.calls[0][0], 0)

    # ------------------------------------------------------------------
    # W2 — reaper interval scales with heartbeat timeout
    # ------------------------------------------------------------------
    def test_reaper_interval_scales_with_heartbeat_timeout(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)

        # 1 min timeout → 30 s interval (clamp floor: 15 s).
        dispatcher._heartbeat_timeout_mins = lambda: 1.0  # type: ignore[assignment]
        self.assertEqual(dispatcher._reaper_interval_seconds(), 30.0)

        # 30 s timeout → 15 s clamp floor.
        dispatcher._heartbeat_timeout_mins = lambda: 0.5  # type: ignore[assignment]
        self.assertEqual(dispatcher._reaper_interval_seconds(), 15.0)

        # 10 min timeout → 60 s clamp ceiling.
        dispatcher._heartbeat_timeout_mins = lambda: 10.0  # type: ignore[assignment]
        self.assertEqual(dispatcher._reaper_interval_seconds(), 60.0)

        # Default fallback when config raises.
        def _boom() -> float:
            raise RuntimeError("no config yet")
        dispatcher._heartbeat_timeout_mins = _boom  # type: ignore[assignment]
        self.assertEqual(dispatcher._reaper_interval_seconds(), 60.0)

    def test_reaper_save_failure_emits_cluster_diagnostic(self) -> None:
        class OneShotStop:
            def __init__(self) -> None:
                self.calls = 0

            def wait(self, _seconds: float) -> bool:
                self.calls += 1
                return self.calls > 1

        class BadRegistry:
            active_count = 1

            def reclaim_stale(self, _timeout: float) -> list:
                return []

            def reclaimed_source_quarantine_snapshot(self) -> list[dict]:
                return []

            def save(self, _path: Path) -> None:
                raise RuntimeError("save denied")

        events: list[dict] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._reaper_stop = OneShotStop()
        dispatcher._reaper_interval_seconds = lambda: 0.0  # type: ignore[assignment]
        dispatcher._heartbeat_timeout_mins = lambda: 5.0  # type: ignore[assignment]
        dispatcher._registry = BadRegistry()
        dispatcher._inflight_state_path = lambda: Path(tempfile.gettempdir()) / "ignored.json"
        dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher._reaper_loop(dispatcher)

        self.assertEqual(events[0]["event"], "inflight_save_failed")
        self.assertIn("during stale-job reaper: save denied", events[0]["message"])
        self.assertIn("Coordinator in-flight registry save failed during stale-job reaper", "\n".join(logs.output))

    def test_reaper_reclaimed_stale_cluster_log_failure_does_not_skip_save(self) -> None:
        class OneShotStop:
            def __init__(self) -> None:
                self.calls = 0

            def wait(self, _seconds: float) -> bool:
                self.calls += 1
                return self.calls > 1

        class Registry:
            active_count = 0

            def __init__(self) -> None:
                self.saved: list[Path] = []

            def reclaim_stale(self, _timeout: float) -> list:
                return [
                    SimpleNamespace(
                        job_id="job-stale",
                        worker_id="worker-1",
                        worker_name="Worker",
                        source_path=r"C:\Media\stale.mkv",
                    )
                ]

            def reclaimed_source_quarantine_snapshot(self) -> list[dict]:
                return []

            def save(self, path: Path) -> None:
                self.saved.append(path)

        registry = Registry()
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._reaper_stop = OneShotStop()
        dispatcher._reaper_interval_seconds = lambda: 0.0  # type: ignore[assignment]
        dispatcher._heartbeat_timeout_mins = lambda: 5.0  # type: ignore[assignment]
        dispatcher._registry = registry
        dispatcher._inflight_state_path = lambda: Path(tempfile.gettempdir()) / "ignored.json"
        dispatcher.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster blocked"))  # type: ignore[assignment]

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher._reaper_loop(dispatcher)

        self.assertEqual(registry.saved, [Path(tempfile.gettempdir()) / "ignored.json"])
        output = "\n".join(logs.output)
        self.assertIn("Failed to emit reclaimed-stale cluster event for job job-stal", output)
        self.assertIn("Reclaimed stale job job-stal", output)

    # ------------------------------------------------------------------
    # W3 — protocol version + accepting_claims surfaced in /api/health
    # ------------------------------------------------------------------
    def test_health_payload_includes_protocol_and_drain_signal(self) -> None:
        from mediapipeline.desktop.network.coordinator import (
            _COORDINATOR_PROTOCOL_VERSION,
        )
        # Protocol version must be a positive int.
        self.assertIsInstance(_COORDINATOR_PROTOCOL_VERSION, int)
        self.assertGreaterEqual(_COORDINATOR_PROTOCOL_VERSION, 1)

    def test_shutdown_flips_accepting_claims(self) -> None:
        """shutdown() must mark the coordinator as not accepting claims
        before tearing down the HTTP server, so a worker hitting
        /api/health during the teardown window learns to back off."""
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._accepting_claims = True
        dispatcher._registry = InFlightRegistry()
        dispatcher._reaper_stop = threading.Event()
        dispatcher._reaper_thread = None
        dispatcher._http_server = None
        dispatcher._mdns = None
        dispatcher._inflight_state_path = lambda: Path(tempfile.gettempdir()) / "ignored.json"
        dispatcher.log_cluster_event = lambda **_kwargs: None  # type: ignore[assignment]
        CoordinatorDispatcher.shutdown(dispatcher)
        self.assertFalse(dispatcher._accepting_claims)

    def test_shutdown_active_count_failure_does_not_block_teardown(self) -> None:
        class BadRegistry:
            saved = False

            @property
            def active_count(self) -> int:
                raise RuntimeError("registry count denied")

            def save(self, _path: Path) -> None:
                self.saved = True

        events: list[dict] = []
        registry = BadRegistry()
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._accepting_claims = True
        dispatcher._registry = registry
        dispatcher._reaper_stop = threading.Event()
        dispatcher._reaper_thread = None
        dispatcher._http_server = None
        dispatcher._mdns = None
        dispatcher._inflight_state_path = lambda: Path(tempfile.gettempdir()) / "ignored.json"
        dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher.shutdown(dispatcher)

        self.assertFalse(dispatcher._accepting_claims)
        self.assertTrue(registry.saved)
        self.assertEqual(events[0]["event"], "coordinator_stopped")
        self.assertIn("active=unknown", events[0]["message"])
        self.assertIn("Coordinator active-count lookup failed during shutdown", "\n".join(logs.output))

    def test_shutdown_cluster_log_failure_does_not_block_teardown(self) -> None:
        class Server:
            def __init__(self) -> None:
                self.shutdown_called = False
                self.close_called = False

            def shutdown(self) -> None:
                self.shutdown_called = True

            def server_close(self) -> None:
                self.close_called = True

        class Mdns:
            def __init__(self) -> None:
                self.stopped = False

            def stop(self) -> None:
                self.stopped = True

        class Registry:
            active_count = 1

            def __init__(self) -> None:
                self.saved: list[Path] = []

            def save(self, path: Path) -> None:
                self.saved.append(path)

        server = Server()
        mdns = Mdns()
        registry = Registry()
        state_path = Path(tempfile.gettempdir()) / "ignored.json"
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._accepting_claims = True
        dispatcher._registry = registry
        dispatcher._reaper_stop = threading.Event()
        dispatcher._reaper_thread = None
        dispatcher._http_server = server
        dispatcher._mdns = mdns
        dispatcher._inflight_state_path = lambda: state_path
        dispatcher.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster blocked"))  # type: ignore[assignment]

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher.shutdown(dispatcher)

        self.assertFalse(dispatcher._accepting_claims)
        self.assertTrue(dispatcher._reaper_stop.is_set())
        self.assertTrue(server.shutdown_called)
        self.assertTrue(server.close_called)
        self.assertTrue(mdns.stopped)
        self.assertIsNone(dispatcher._http_server)
        self.assertIsNone(dispatcher._mdns)
        self.assertEqual(registry.saved, [state_path])
        self.assertIn("Failed to emit coordinator-stopped cluster event", "\n".join(logs.output))

    def test_shutdown_logs_teardown_failures_and_stuck_reaper(self) -> None:
        class BadServer:
            def shutdown(self) -> None:
                raise RuntimeError("shutdown denied")

            def server_close(self) -> None:
                raise RuntimeError("close denied")

        class BadMdns:
            def stop(self) -> None:
                raise RuntimeError("mdns denied")

        class StuckReaper:
            def __init__(self) -> None:
                self.timeout: float | None = None

            def join(self, timeout: float) -> None:
                self.timeout = timeout

            def is_alive(self) -> bool:
                return True

        class BadRegistry:
            active_count = 1

            def save(self, _path: Path) -> None:
                raise RuntimeError("save denied")

        reaper = StuckReaper()
        events: list[dict] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._accepting_claims = True
        dispatcher._registry = BadRegistry()
        dispatcher._reaper_stop = threading.Event()
        dispatcher._reaper_thread = reaper
        dispatcher._http_server = BadServer()
        dispatcher._mdns = BadMdns()
        dispatcher._inflight_state_path = lambda: Path(tempfile.gettempdir()) / "ignored.json"
        dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher.shutdown(dispatcher)

        text = "\n".join(logs.output)
        self.assertIn("Coordinator HTTP server shutdown failed: shutdown denied", text)
        self.assertIn("Coordinator HTTP server close failed: close denied", text)
        self.assertIn("Coordinator mDNS advertiser stop failed: mdns denied", text)
        self.assertIn("Coordinator stale-job reaper did not stop within 2.0 seconds.", text)
        self.assertIn("Coordinator in-flight registry save failed during shutdown: save denied", text)
        self.assertEqual(reaper.timeout, 2.0)
        self.assertFalse(dispatcher._accepting_claims)
        self.assertIsNone(dispatcher._http_server)
        self.assertIsNone(dispatcher._mdns)
        self.assertEqual(events[0]["event"], "coordinator_stopped")
        self.assertEqual(events[1]["event"], "inflight_save_failed")
        self.assertIn("during coordinator shutdown: save denied", events[1]["message"])

    def test_claim_returns_empty_while_coordinator_is_draining(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._accepting_claims = False
        dispatcher._compute_retry_after_seconds = lambda: 5  # type: ignore[assignment]
        dispatcher._scan_for_next_record = lambda _worker_name: self.fail("draining claim should not scan")

        sent: list[tuple[dict, int]] = []
        handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))

        CoordinatorDispatcher._http_claim(
            dispatcher,
            handler,  # type: ignore[arg-type]
            {"worker_id": "worker-1", "worker_name": "worker-box"},
        )

        self.assertEqual(sent[0][1], 200)
        self.assertEqual(sent[0][0]["status"], "empty")
        self.assertEqual(sent[0][0]["retry_after_seconds"], 5)

    def test_claim_empty_persists_idle_worker_row_for_coordinator_board(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "coordinator_inflight.json"
            registry = InFlightRegistry()
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._accepting_claims = True
            dispatcher._claim_lock = threading.Lock()
            dispatcher._registry = registry
            dispatcher._scan_for_next_record = lambda _worker_name: (None, {})  # type: ignore[assignment]
            dispatcher._compute_retry_after_seconds = lambda: 11  # type: ignore[assignment]
            dispatcher._inflight_state_path = lambda: state_path  # type: ignore[assignment]
            dispatcher._safe_log_cluster_event = lambda *_args, **_kwargs: None  # type: ignore[assignment]
            sent: list[tuple[dict, int]] = []
            handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))

            CoordinatorDispatcher._http_claim(
                dispatcher,
                handler,  # type: ignore[arg-type]
                {"worker_id": "worker-1", "worker_name": "Worker One"},
            )

            restored = InFlightRegistry()
            self.assertTrue(restored.load(state_path))
            rows = restored.idle_workers_snapshot()

        self.assertEqual(sent[0][1], 200)
        self.assertEqual(sent[0][0]["status"], "empty")
        self.assertEqual(sent[0][0]["retry_after_seconds"], 11)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].worker_id, "worker-1")
        self.assertEqual(rows[0].worker_name, "Worker One")
        self.assertEqual(rows[0].status, "idle")
        self.assertTrue(rows[0].last_heartbeat)

    def test_http_claim_skips_records_outside_worker_accessible_libraries(self) -> None:
        tv_record = SimpleNamespace(
            source_path=r"C:\Coord\TV\Show\S01E01.mkv",
            library_id="tv",
            relative_path=r"Show\S01E01.mkv",
            priority=False,
            estimated_size_gb=1.0,
        )
        movie_record = SimpleNamespace(
            source_path=r"C:\Coord\Movies\Movie.mkv",
            library_id="movies",
            relative_path="Movie.mkv",
            priority=False,
            estimated_size_gb=2.0,
        )
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "coordinator_inflight.json"
            registry = InFlightRegistry()
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._accepting_claims = True
            dispatcher._claim_lock = threading.Lock()
            dispatcher._registry = registry
            dispatcher._app = SimpleNamespace(
                queue_records=[tv_record, movie_record],
                failure_records=[],
                resolved=SimpleNamespace(config_data={}),
            )
            dispatcher._config = lambda: {}  # type: ignore[assignment]
            dispatcher._snapshot_encode_config = lambda worker_name="", record=None: {"worker": worker_name}  # type: ignore[assignment]
            dispatcher._compute_retry_after_seconds = lambda: 11  # type: ignore[assignment]
            dispatcher._inflight_state_path = lambda: state_path  # type: ignore[assignment]
            dispatcher._safe_log_cluster_event = lambda *_args, **_kwargs: None  # type: ignore[assignment]
            sent: list[tuple[dict, int]] = []
            handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))

            CoordinatorDispatcher._http_claim(
                dispatcher,
                handler,  # type: ignore[arg-type]
                {
                    "worker_id": "worker-1",
                    "worker_name": "Worker One",
                    "accessible_library_ids": "Movies",
                },
            )

            rows = registry.snapshot()

        payload = sent[-1][0]
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["source_path"], movie_record.source_path)
        self.assertEqual(payload["library_id"], "movies")
        self.assertFalse(registry.is_in_flight(tv_record.source_path))
        self.assertEqual(rows[0].accessible_library_ids, ["Movies"])

    def test_scan_with_explicit_empty_accessible_libraries_hands_no_library_jobs(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._registry = InFlightRegistry()
        dispatcher._app = SimpleNamespace(
            queue_records=[
                SimpleNamespace(source_path=r"C:\Coord\TV\Show\S01E01.mkv", library_id="tv"),
                SimpleNamespace(source_path=r"C:\Coord\Movies\Movie.mkv", library_id="movies"),
            ]
        )
        dispatcher._snapshot_encode_config = lambda worker_name="", record=None: {"worker": worker_name}  # type: ignore[assignment]
        dispatcher._coordinator_max_job_retries = lambda: 3  # type: ignore[assignment]

        record, encode_config = CoordinatorDispatcher._scan_for_next_record(
            dispatcher,
            "Worker One",
            worker_id="worker-1",
            max_job_retries=3,
            accessible_library_ids=[],
        )

        self.assertIsNone(record)
        self.assertEqual(encode_config, {})

    def test_claim_rejection_logs_missing_and_invalid_worker_id(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        sent: list[tuple[dict, int]] = []
        handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher._http_claim(dispatcher, handler, {})  # type: ignore[arg-type]
            CoordinatorDispatcher._http_claim(dispatcher, handler, {"worker_id": "bad worker"})  # type: ignore[arg-type]

        self.assertEqual(sent[0][1], 400)
        self.assertEqual(sent[0][0]["error"], "worker_id query parameter is required")
        self.assertEqual(sent[1][1], 400)
        self.assertIn("worker_id must be 1..64 chars", sent[1][0]["error"])
        text = "\n".join(logs.output)
        self.assertIn("Rejected /api/claim with missing worker_id", text)
        self.assertIn("Rejected /api/claim with invalid worker_id='bad worker'", text)

    def test_http_claim_registry_failure_returns_logged_500(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._accepting_claims = True
        dispatcher._claim_lock = threading.Lock()
        dispatcher._scan_for_next_record = lambda _worker_name: (  # type: ignore[assignment]
            SimpleNamespace(source_path=str(Path.cwd() / "movie.mkv"), priority=False),
            {},
        )
        dispatcher._registry = SimpleNamespace(
            claim=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("claim exploded"))
        )
        sent: list[tuple[dict, int]] = []
        handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="ERROR") as logs:
            CoordinatorDispatcher._http_claim(
                dispatcher,
                handler,  # type: ignore[arg-type]
                {"worker_id": "worker-1", "worker_name": "worker-box"},
            )

        self.assertEqual(sent, [({"error": "claim unavailable"}, 500)])
        self.assertIn("Failed to process /api/claim for worker worker-1", "\n".join(logs.output))

    def test_coordinator_inflight_save_failures_emit_cluster_diagnostics(self) -> None:
        events: list[dict] = []

        def make_dispatcher(registry: InFlightRegistry) -> CoordinatorDispatcher:
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._registry = registry
            dispatcher._inflight_state_path = lambda: Path("coordinator_inflight.json")  # type: ignore[assignment]
            dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]
            return dispatcher

        claim_registry = InFlightRegistry()
        claim_dispatcher = make_dispatcher(claim_registry)
        claim_dispatcher._accepting_claims = True
        claim_dispatcher._claim_lock = threading.Lock()
        claim_dispatcher._scan_for_next_record = lambda _worker_name: (  # type: ignore[assignment]
            SimpleNamespace(source_path=r"C:\Media\claim.mkv", priority=False),
            {},
        )
        claim_dispatcher._source_has_prior_failure = lambda _source_path: False  # type: ignore[assignment]
        claim_sent: list[tuple[dict, int]] = []
        claim_handler = SimpleNamespace(_send_json=lambda payload, status=200: claim_sent.append((payload, status)))

        with (
            patch.object(claim_registry, "save", side_effect=OSError("claim save denied")),
            self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as claim_logs,
        ):
            CoordinatorDispatcher._http_claim(
                claim_dispatcher,
                claim_handler,  # type: ignore[arg-type]
                {"worker_id": "worker-1", "worker_name": "Worker"},
            )
        self.assertEqual(claim_sent, [({"error": "claim state unavailable"}, 503)])
        self.assertFalse(claim_registry.is_in_flight(r"C:\Media\claim.mkv"))

        release_registry = InFlightRegistry()
        release_registry.claim(
            job_id="job-release",
            worker_id="worker-1",
            worker_name="Worker",
            source_path=r"C:\Media\release.mkv",
            encode_config={},
        )
        release_dispatcher = make_dispatcher(release_registry)
        release_sent: list[tuple[dict, int]] = []
        release_handler = SimpleNamespace(_send_json=lambda payload, status=200: release_sent.append((payload, status)))
        release_body = json.dumps(
            DoneRequest(job_id="job-release", worker_id="worker-1", released=True).to_dict()
        ).encode("utf-8")

        with (
            patch.object(release_registry, "save", side_effect=OSError("release save denied")),
            self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as release_logs,
        ):
            CoordinatorDispatcher._http_done(release_dispatcher, release_handler, release_body)  # type: ignore[arg-type]
        self.assertEqual(release_sent, [({"error": "done state unavailable"}, 503)])
        self.assertTrue(release_registry.is_active("job-release", "worker-1"))

        done_registry = InFlightRegistry()
        done_registry.claim(
            job_id="job-done",
            worker_id="worker-1",
            worker_name="Worker",
            source_path=r"C:\Media\done.mkv",
            encode_config={},
        )
        done_dispatcher = make_dispatcher(done_registry)
        done_sent: list[tuple[dict, int]] = []
        done_handler = SimpleNamespace(_send_json=lambda payload, status=200: done_sent.append((payload, status)))
        done_body = json.dumps(
            DoneRequest(job_id="job-done", worker_id="worker-1", success=False).to_dict()
        ).encode("utf-8")

        with (
            patch.object(done_registry, "save", side_effect=OSError("done save denied")),
            self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as done_logs,
        ):
            CoordinatorDispatcher._http_done(done_dispatcher, done_handler, done_body)  # type: ignore[arg-type]
        self.assertEqual(done_sent, [({"error": "done state unavailable"}, 503)])
        self.assertTrue(done_registry.is_active("job-done", "worker-1"))

        save_events = [event for event in events if event.get("event") == "inflight_save_failed"]
        self.assertEqual(len(save_events), 3)
        self.assertIn("Claim denied because in-flight registry could not be saved: claim save denied", save_events[0]["message"])
        self.assertEqual(save_events[0]["source_path"], r"C:\Media\claim.mkv")
        self.assertIn("after worker release: release save denied", save_events[1]["message"])
        self.assertEqual(save_events[1]["job_id"], "job-release")
        self.assertIn("after done report: done save denied", save_events[2]["message"])
        self.assertEqual(save_events[2]["job_id"], "job-done")
        self.assertIn("Failed to save registry after claim", "\n".join(claim_logs.output))
        self.assertIn("Failed to save inflight state after worker release", "\n".join(release_logs.output))
        self.assertIn("Failed to save registry after done report", "\n".join(done_logs.output))

    def test_http_claim_rolls_back_when_response_payload_is_not_serializable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._accepting_claims = True
            dispatcher._claim_lock = threading.Lock()
            dispatcher._registry = InFlightRegistry()
            dispatcher._inflight_state_path = lambda: Path(td) / "coordinator_inflight.json"  # type: ignore[assignment]
            dispatcher._safe_log_cluster_event = lambda *_args, **_kwargs: None  # type: ignore[assignment]
            dispatcher._scan_for_next_record = lambda _worker_name: (  # type: ignore[assignment]
                SimpleNamespace(source_path=r"C:\Media\claim.mkv", priority=False),
                {"bad": float("nan")},
            )
            dispatcher._source_has_prior_failure = lambda _source_path: False  # type: ignore[assignment]
            sent: list[tuple[dict, int]] = []
            handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))

            with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
                CoordinatorDispatcher._http_claim(
                    dispatcher,
                    handler,  # type: ignore[arg-type]
                    {"worker_id": "worker-1", "worker_name": "Worker"},
                )

        self.assertEqual(sent, [({"error": "claim unavailable"}, 500)])
        self.assertFalse(dispatcher._registry.is_in_flight(r"C:\Media\claim.mkv"))
        self.assertIn("could not be serialized; rolling back claim", "\n".join(logs.output))

    def test_http_claim_rolls_back_and_persists_when_response_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "coordinator_inflight.json"
            registry = InFlightRegistry()
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._accepting_claims = True
            dispatcher._claim_lock = threading.Lock()
            dispatcher._registry = registry
            dispatcher._inflight_state_path = lambda: state_path  # type: ignore[assignment]
            dispatcher._safe_log_cluster_event = lambda *_args, **_kwargs: None  # type: ignore[assignment]
            dispatcher._scan_for_next_record = lambda _worker_name: (  # type: ignore[assignment]
                SimpleNamespace(source_path=r"C:\Media\claim.mkv", priority=False),
                {},
            )
            dispatcher._source_has_prior_failure = lambda _source_path: False  # type: ignore[assignment]

            def failing_send(_payload: dict, status: int = 200) -> None:
                raise RuntimeError("socket closed")

            handler = SimpleNamespace(_send_json=failing_send)

            with self.assertRaisesRegex(RuntimeError, "socket closed"):
                CoordinatorDispatcher._http_claim(
                    dispatcher,
                    handler,  # type: ignore[arg-type]
                    {"worker_id": "worker-1", "worker_name": "Worker"},
                )

            restored = InFlightRegistry()
            self.assertTrue(restored.load(state_path))

        self.assertFalse(registry.is_in_flight(r"C:\Media\claim.mkv"))
        self.assertEqual(restored.active_count, 0)

    def test_http_claim_allows_only_one_concurrent_worker_for_same_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "coordinator_inflight.json"
            record = SimpleNamespace(
                source_path=r"C:\Media\same.mkv",
                priority=False,
                estimated_size_gb=1.0,
                library_id="movies",
            )
            registry = InFlightRegistry()
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._accepting_claims = True
            dispatcher._claim_lock = threading.Lock()
            dispatcher._registry = registry
            dispatcher._app = SimpleNamespace(
                queue_records=[record],
                failure_records=[],
                _queue_lock=threading.Lock(),
                resolved=SimpleNamespace(config_data={}),
            )
            dispatcher._config = lambda: {}  # type: ignore[assignment]
            dispatcher._inflight_state_path = lambda: state_path  # type: ignore[assignment]
            dispatcher._safe_log_cluster_event = lambda *_args, **_kwargs: None  # type: ignore[assignment]
            sent: list[tuple[str, dict, int]] = []
            start = threading.Barrier(2)

            def claim(worker_id: str) -> None:
                start.wait(timeout=5)
                handler = SimpleNamespace(
                    _send_json=lambda payload, status=200: sent.append((worker_id, payload, status))
                )
                CoordinatorDispatcher._http_claim(
                    dispatcher,
                    handler,  # type: ignore[arg-type]
                    {"worker_id": worker_id, "worker_name": worker_id},
                )

            threads = [threading.Thread(target=claim, args=(f"worker-{index}",)) for index in (1, 2)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=5)

        self.assertEqual(len(sent), 2)
        ok = [payload for _worker, payload, status in sent if status == 200 and payload["status"] == "ok"]
        empty = [payload for _worker, payload, status in sent if status == 200 and payload["status"] == "empty"]
        self.assertEqual(len(ok), 1)
        self.assertEqual(len(empty), 1)
        self.assertEqual(registry.active_count, 1)
        self.assertTrue(registry.is_in_flight("c:/media/same.mkv"))

    def test_remove_from_queue_uses_normalized_source_identity(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        kept = SimpleNamespace(source_path=r"C:\Media\other.mkv")
        dispatcher._app = SimpleNamespace(
            queue_records=[
                SimpleNamespace(source_path=r"C:\Media\Movie.mkv"),
                kept,
            ],
            _queue_lock=threading.Lock(),
            apply_queue_filters=lambda: None,
        )

        CoordinatorDispatcher._remove_from_queue(dispatcher, "c:/media/movie.mkv")

        self.assertEqual(dispatcher._app.queue_records, [kept])

    def test_http_claim_cluster_log_failure_does_not_block_claim_response(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = r"C:\Media\claim.mkv"
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._accepting_claims = True
            dispatcher._claim_lock = threading.Lock()
            dispatcher._registry = InFlightRegistry()
            dispatcher._scan_for_next_record = lambda _worker_name: (  # type: ignore[assignment]
                SimpleNamespace(source_path=source, priority=True, estimated_size_gb=1.5),
                {"preset": "fast"},
            )
            dispatcher._source_has_prior_failure = lambda _source_path: False  # type: ignore[assignment]
            dispatcher._inflight_state_path = lambda: Path(td) / "inflight_registry.json"  # type: ignore[assignment]
            dispatcher.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster blocked"))  # type: ignore[assignment]
            sent: list[tuple[dict, int]] = []
            handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))

            with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
                CoordinatorDispatcher._http_claim(
                    dispatcher,
                    handler,  # type: ignore[arg-type]
                    {"worker_id": "worker-1", "worker_name": "Worker"},
                )

            self.assertEqual(sent[0][1], 200)
            self.assertEqual(sent[0][0]["status"], "ok")
            self.assertEqual(sent[0][0]["source_path"], source)
            self.assertTrue(dispatcher._registry.is_in_flight(source))
            self.assertIn("Failed to emit claim-handed cluster event for job ", "\n".join(logs.output))
            self.assertIn("cluster blocked", "\n".join(logs.output))

    def test_http_claim_releases_claim_when_retry_policy_fails(self) -> None:
        class FakeRegistry:
            def __init__(self) -> None:
                self.claims: list[dict[str, object]] = []
                self.releases: list[tuple[str, str]] = []

            def claim(self, **kwargs) -> bool:
                self.claims.append(kwargs)
                return True

            def unclaim(self, job_id: str, worker_id: str):
                self.releases.append((job_id, worker_id))
                return SimpleNamespace(job_id=job_id)

        registry = FakeRegistry()
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._accepting_claims = True
        dispatcher._claim_lock = threading.Lock()
        dispatcher._scan_for_next_record = lambda _worker_name: (  # type: ignore[assignment]
            SimpleNamespace(source_path=str(Path.cwd() / "movie.mkv"), priority=False),
            {},
        )
        dispatcher._registry = registry
        dispatcher._source_has_prior_failure = lambda _source_path: (_ for _ in ()).throw(RuntimeError("failure records unreadable"))  # type: ignore[assignment]
        sent: list[tuple[dict, int]] = []
        handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="ERROR") as logs:
            CoordinatorDispatcher._http_claim(
                dispatcher,
                handler,  # type: ignore[arg-type]
                {"worker_id": "worker-1", "worker_name": "worker-box"},
            )

        self.assertEqual(sent, [({"error": "claim unavailable"}, 500)])
        self.assertEqual(len(registry.claims), 1)
        self.assertEqual(registry.releases, [(str(registry.claims[0]["job_id"]), "worker-1")])
        output = "\n".join(logs.output)
        self.assertIn("Failed to evaluate retry policy after claim", output)
        self.assertIn("failure records unreadable", output)

    def test_done_report_for_unknown_job_is_logged_to_cluster(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._registry = InFlightRegistry()
        events: list[dict] = []
        dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]
        sent: list[tuple[dict, int]] = []
        handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))
        body = json.dumps(
            DoneRequest(job_id="job-missing", worker_id="worker-1", success=True).to_dict()
        ).encode("utf-8")

        CoordinatorDispatcher._http_done(dispatcher, handler, body)  # type: ignore[arg-type]

        self.assertEqual(sent, [({"status": "not_found", "job_id": "job-missing"}, 404)])
        self.assertEqual(events[0]["event"], "done_not_found")
        self.assertEqual(events[0]["worker_id"], "worker-1")
        self.assertEqual(events[0]["job_id"], "job-missing")

    def test_late_done_after_stale_reclaim_is_recorded_durably(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "coordinator_inflight.json"
            registry = InFlightRegistry()
            registry.claim(
                job_id="job-stale",
                worker_id="worker-1",
                worker_name="Worker",
                source_path=r"C:\Media\stale.mkv",
                encode_config={},
            )
            with registry._lock:
                registry._jobs["job-stale"].last_heartbeat = "2026-01-01T00:00:00+00:00"
            self.assertEqual([job.job_id for job in registry.reclaim_stale(0.01)], ["job-stale"])

            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._registry = registry
            dispatcher._inflight_state_path = lambda: state_path  # type: ignore[assignment]
            dispatcher._remove_from_queue = lambda _source_path: None  # type: ignore[assignment]
            events: list[dict] = []
            dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]
            sent: list[tuple[dict, int]] = []
            handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))
            body = json.dumps(
                DoneRequest(
                    job_id="job-stale",
                    worker_id="worker-1",
                    success=True,
                    completion_status="processed",
                    publish_state="pending_publish",
                    publish_mode="deferred",
                    output_path=r"C:\Out\stale.mkv",
                ).to_dict()
            ).encode("utf-8")

            CoordinatorDispatcher._http_done(dispatcher, handler, body)  # type: ignore[arg-type]

            restored = InFlightRegistry()
            self.assertTrue(restored.load(state_path))

        self.assertEqual(sent, [({"status": "late_recorded", "job_id": "job-stale", "source_path": r"C:\Media\stale.mkv"}, 200)])
        reports = restored.late_terminal_reports_snapshot()
        self.assertEqual(len(reports), 1)
        self.assertEqual(reports[0]["job_id"], "job-stale")
        self.assertEqual(reports[0]["source_path"], r"C:\Media\stale.mkv")
        self.assertEqual(reports[0]["publish_state"], "pending_publish")
        self.assertEqual(events[0]["event"], "late_terminal_accepted")
        self.assertEqual(restored.active_count, 0)

    def test_release_report_for_unknown_job_is_logged_to_cluster(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._registry = InFlightRegistry()
        events: list[dict] = []
        dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]
        sent: list[tuple[dict, int]] = []
        handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))
        body = json.dumps(
            DoneRequest(job_id="job-missing", worker_id="worker-1", released=True).to_dict()
        ).encode("utf-8")

        CoordinatorDispatcher._http_done(dispatcher, handler, body)  # type: ignore[arg-type]

        self.assertEqual(sent, [({"status": "not_found", "job_id": "job-missing"}, 404)])
        self.assertEqual(events[0]["event"], "release_not_found")
        self.assertEqual(events[0]["worker_id"], "worker-1")
        self.assertEqual(events[0]["job_id"], "job-missing")

    def test_done_report_cluster_log_failures_do_not_block_http_response(self) -> None:
        cases = (
            (
                "done-not-found",
                InFlightRegistry(),
                DoneRequest(job_id="job-missing", worker_id="worker-1", success=True),
                {"status": "not_found", "job_id": "job-missing"},
                404,
                "Failed to emit done-not-found cluster event for job job-miss",
            ),
            (
                "release-not-found",
                InFlightRegistry(),
                DoneRequest(job_id="job-missing", worker_id="worker-1", released=True),
                {"status": "not_found", "job_id": "job-missing"},
                404,
                "Failed to emit release-not-found cluster event for job job-miss",
            ),
        )

        for name, registry, request, expected_payload, expected_status, expected_log in cases:
            with self.subTest(name=name):
                dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
                dispatcher._registry = registry
                dispatcher.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster blocked"))  # type: ignore[assignment]
                sent: list[tuple[dict, int]] = []
                handler = SimpleNamespace(_send_json=lambda payload, status=200, sent=sent: sent.append((payload, status)))

                with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
                    CoordinatorDispatcher._http_done(
                        dispatcher,
                        handler,  # type: ignore[arg-type]
                        json.dumps(request.to_dict()).encode("utf-8"),
                    )

                self.assertEqual(sent, [(expected_payload, expected_status)])
                self.assertIn(expected_log, "\n".join(logs.output))

        registry = InFlightRegistry()
        registry.claim(
            job_id="job-owned",
            worker_id="owner-1",
            worker_name="Owner",
            source_path=r"C:\Media\owned.mkv",
            encode_config={},
        )
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._registry = registry
        dispatcher.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster blocked"))  # type: ignore[assignment]
        sent: list[tuple[dict, int]] = []
        handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher._http_done(
                dispatcher,
                handler,  # type: ignore[arg-type]
                json.dumps(
                    DoneRequest(job_id="job-owned", worker_id="other-1", success=True).to_dict()
                ).encode("utf-8"),
            )

        self.assertEqual(sent[0][1], 403)
        self.assertEqual(sent[0][0]["status"], "forbidden")
        self.assertIn("Failed to emit done-owner-mismatch cluster event for job job-owne", "\n".join(logs.output))

    # ------------------------------------------------------------------
    # W6 — /api/workers includes coordinator wall clock
    # ------------------------------------------------------------------
    def test_workers_response_carries_coordinator_now(self) -> None:
        from mediapipeline.desktop.network.protocol import WorkersResponse
        resp = WorkersResponse(coordinator_now="2026-05-08T12:34:56-04:00")
        self.assertEqual(
            resp.to_dict()["coordinator_now"],
            "2026-05-08T12:34:56-04:00",
        )
        # Default (omitted) coerces to empty string, not missing key.
        self.assertEqual(WorkersResponse().to_dict()["coordinator_now"], "")

    def test_workers_response_snapshot_failure_returns_logged_500(self) -> None:
        class BadRegistry:
            def snapshot(self) -> list[object]:
                raise RuntimeError("snapshot denied")

        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._registry = BadRegistry()
        dispatcher._app = SimpleNamespace(queue_records=[1, 2, 3])
        sent: list[tuple[dict, int]] = []
        handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="ERROR") as logs:
            CoordinatorDispatcher._http_workers(dispatcher, handler, {})  # type: ignore[arg-type]

        self.assertEqual(sent, [({"error": "worker snapshot unavailable"}, 500)])
        self.assertIn("Failed to build /api/workers response: snapshot denied", "\n".join(logs.output))

    # ------------------------------------------------------------------
    # W7 — cluster log is keyed off coordinator receive time, with the
    # worker-supplied timestamp preserved as a forensic tag.
    # ------------------------------------------------------------------
    def test_cluster_log_renders_worker_timestamp_when_skewed(self) -> None:
        from mediapipeline.desktop.network.protocol import LogEntryRequest

        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        entry = LogEntryRequest(
            timestamp="2026-05-08T12:00:00-04:00",       # coordinator-stamped
            worker_id="w1",
            worker_name="worker-pc",
            role="worker",
            level="INFO",
            event="job_completed",
            message="ok",
        )
        # Worker reported a timestamp 10 minutes off from coordinator.
        entry._worker_ts = "2026-05-08T11:50:00-04:00"  # type: ignore[attr-defined]
        line = CoordinatorDispatcher._format_cluster_log_line(dispatcher, entry)
        direct_line = format_cluster_log_line(entry)
        # Coordinator timestamp leads the line.
        self.assertTrue(line.startswith("2026-05-08T12:00:00-04:00"))
        # Worker timestamp is preserved as a tag.
        self.assertIn("worker_ts=2026-05-08T11:50:00-04:00", line)
        self.assertEqual(direct_line, line)

    def test_cluster_log_rotation_failure_is_logged_without_blocking_append(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "cluster.log"
            log_path.write_text("existing\n", encoding="utf-8")
            # Force the backup path to fail `unlink()` on all platforms.
            (Path(tmp) / "cluster.log.1").mkdir()

            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._cluster_log_lock = threading.Lock()
            dispatcher._cluster_log_max_bytes = 1
            dispatcher.cluster_log_path = lambda: log_path  # type: ignore[method-assign]

            entry = LogEntryRequest(
                timestamp="2026-05-08T12:00:00-04:00",
                worker_id="w1",
                worker_name="worker-pc",
                role="worker",
                level="INFO",
                event="rotation_test",
                message="append should continue",
            )

            with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
                CoordinatorDispatcher._append_cluster_log(dispatcher, entry)

            output = "\n".join(logs.output)
            self.assertIn("Failed to rotate cluster log", output)
            self.assertIn("cluster.log", output)
            self.assertIn("rotation_test", log_path.read_text(encoding="utf-8"))

    def test_cluster_log_size_inspection_failure_is_logged_without_blocking_append(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "cluster.log"
            log_path.write_text("existing\n", encoding="utf-8")

            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._cluster_log_lock = threading.Lock()
            dispatcher._cluster_log_max_bytes = 1
            dispatcher.cluster_log_path = lambda: log_path  # type: ignore[method-assign]

            entry = LogEntryRequest(
                timestamp="2026-05-08T12:00:00-04:00",
                worker_id="w1",
                worker_name="worker-pc",
                role="worker",
                level="INFO",
                event="stat_test",
                message="append should continue",
            )

            original_stat = Path.stat

            def fake_stat(path: Path, *args, **kwargs):
                if path == log_path:
                    raise OSError("stat denied")
                return original_stat(path, *args, **kwargs)

            with patch.object(Path, "stat", fake_stat):
                with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
                    CoordinatorDispatcher._append_cluster_log(dispatcher, entry)

            output = "\n".join(logs.output)
            self.assertIn("Failed to inspect cluster log size", output)
            self.assertIn("stat denied", output)
            self.assertIn("stat_test", log_path.read_text(encoding="utf-8"))

    def test_cluster_log_path_resolution_failure_is_logged_without_raising(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher.cluster_log_path = lambda: (_ for _ in ()).throw(RuntimeError("state path unavailable"))  # type: ignore[method-assign]
        entry = LogEntryRequest(
            timestamp="2026-05-08T12:00:00-04:00",
            worker_id="w1",
            worker_name="worker-pc",
            role="worker",
            level="INFO",
            event="path_resolution_test",
            message="path lookup should not escape",
        )

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="ERROR") as logs:
            CoordinatorDispatcher._append_cluster_log(dispatcher, entry)

        output = "\n".join(logs.output)
        self.assertIn("Failed to resolve cluster log path", output)
        self.assertIn("state path unavailable", output)

    def test_cluster_log_format_failure_is_logged_without_raising(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "cluster.log"
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._cluster_log_lock = threading.Lock()
            dispatcher._cluster_log_max_bytes = 1
            dispatcher.cluster_log_path = lambda: log_path  # type: ignore[method-assign]
            dispatcher._format_cluster_log_line = lambda _entry: (_ for _ in ()).throw(RuntimeError("format blocked"))  # type: ignore[method-assign]
            entry = LogEntryRequest(
                timestamp="2026-05-08T12:00:00-04:00",
                worker_id="w1",
                worker_name="worker-pc",
                role="worker",
                level="INFO",
                event="format_test",
                message="format should not escape",
            )

            with self.assertLogs("mediapipeline.desktop.network.coordinator", level="ERROR") as logs:
                CoordinatorDispatcher._append_cluster_log(dispatcher, entry)

            output = "\n".join(logs.output)
            self.assertIn("Failed to prepare or append cluster log", output)
            self.assertIn("format blocked", output)
            self.assertFalse(log_path.exists())

    # ------------------------------------------------------------------
    # W4 — empty ClaimResponse carries a backoff hint, worker honours it
    # while clamping to its configured poll interval ceiling.
    # ------------------------------------------------------------------
    def test_claim_response_retry_after_seconds_round_trips(self) -> None:
        wire = ClaimResponse.empty(retry_after_seconds=7).to_dict()
        self.assertEqual(wire["status"], "empty")
        self.assertEqual(wire["retry_after_seconds"], 7)
        # Round-trip back into a dataclass instance preserves the value.
        rebuilt = ClaimResponse.from_dict(wire)
        self.assertEqual(rebuilt.retry_after_seconds, 7)

    def test_claim_response_missing_retry_after_seconds_defaults_to_zero(self) -> None:
        """Old coordinators that don't advertise the field must still
        deserialise cleanly into a ClaimResponse with a 0 hint, which
        the worker treats as 'use my configured interval'."""
        legacy_wire = {
            "status": "empty",
            "job_id": "",
            "source_path": "",
            "priority": False,
            "estimated_size_gb": 0.0,
            "encode_config": {},
            "retry_on_failure": True,
        }
        rebuilt = ClaimResponse.from_dict(legacy_wire)
        self.assertEqual(rebuilt.retry_after_seconds, 0)

    def test_compute_retry_after_seconds_reflects_registry_activity(self) -> None:
        from mediapipeline.desktop.network.coordinator_policy import (
            RETRY_AFTER_ACTIVE_SECONDS, RETRY_AFTER_IDLE_SECONDS,
        )
        # Idle cluster → long backoff.
        idle_dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        idle_dispatcher._registry = InFlightRegistry()
        self.assertEqual(
            CoordinatorDispatcher._compute_retry_after_seconds(idle_dispatcher),
            RETRY_AFTER_IDLE_SECONDS,
        )

        # Active cluster → short backoff.
        active_dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        active_dispatcher._registry = InFlightRegistry()
        active_dispatcher._registry.claim(
            job_id="active-1", worker_id="alice", worker_name="alice-pc",
            source_path=r"\\share\foo.mkv", encode_config={},
        )
        self.assertEqual(
            CoordinatorDispatcher._compute_retry_after_seconds(active_dispatcher),
            RETRY_AFTER_ACTIVE_SECONDS,
        )
        # Active hint must be strictly shorter than idle hint.
        self.assertLess(RETRY_AFTER_ACTIVE_SECONDS, RETRY_AFTER_IDLE_SECONDS)

    def test_compute_retry_after_seconds_logs_registry_count_failure(self) -> None:
        from mediapipeline.desktop.network.coordinator_policy import RETRY_AFTER_IDLE_SECONDS

        class BadRegistry:
            @property
            def active_count(self) -> int:
                raise RuntimeError("registry offline")

        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._registry = BadRegistry()

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            retry_after = CoordinatorDispatcher._compute_retry_after_seconds(dispatcher)

        self.assertEqual(retry_after, RETRY_AFTER_IDLE_SECONDS)
        self.assertIn(
            "Could not read active in-flight job count; using idle retry hint: registry offline",
            "\n".join(logs.output),
        )

    def test_http_claim_tolerates_invalid_queue_record_estimated_size(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            source = r"C:\Media\movie.mkv"
            record = SimpleNamespace(source_path=source, priority=False, estimated_size_gb="not-a-number")
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._accepting_claims = True
            dispatcher._claim_lock = threading.Lock()
            dispatcher._registry = InFlightRegistry()
            dispatcher._scan_for_next_record = lambda _worker_name: (record, {})  # type: ignore[assignment]
            dispatcher._source_has_prior_failure = lambda _source_path: False  # type: ignore[assignment]
            dispatcher._inflight_state_path = lambda: Path(td) / "inflight_registry.json"  # type: ignore[assignment]
            dispatcher.log_cluster_event = lambda **_kwargs: None  # type: ignore[assignment]
            sent: list[tuple[dict[str, object], int]] = []
            handler = SimpleNamespace(_send_json=lambda payload, status=200: sent.append((payload, status)))

            with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
                CoordinatorDispatcher._http_claim(
                    dispatcher,
                    handler,  # type: ignore[arg-type]
                    {"worker_id": "worker-1", "worker_name": "Worker"},
                )

        self.assertEqual(sent[0][1], 200)
        self.assertEqual(sent[0][0]["status"], "ok")
        self.assertEqual(sent[0][0]["estimated_size_gb"], 0.0)
        self.assertIn("Invalid estimated_size_gb for queue record", "\n".join(logs.output))

    def test_worker_resolve_wait_seconds_clamps_server_hint(self) -> None:
        worker = WorkerDispatcher.__new__(WorkerDispatcher)
        worker._poll_interval = 30  # type: ignore[attr-defined]

        # No hint → fall back to the configured interval.
        self.assertEqual(WorkerDispatcher._resolve_wait_seconds(worker, 0), 30.0)
        self.assertEqual(WorkerDispatcher._resolve_wait_seconds(worker, -5), 30.0)

        # Reasonable hint shorter than ceiling → honour it.
        self.assertEqual(WorkerDispatcher._resolve_wait_seconds(worker, 5), 5.0)

        # Hint longer than ceiling → clamped down so the operator's
        # configured cadence is the upper bound. A buggy coordinator
        # cannot make this worker poll less often than configured.
        self.assertEqual(WorkerDispatcher._resolve_wait_seconds(worker, 600), 30.0)

        # Sub-second hint → clamped up to 1 s so the worker can't be
        # induced into a tight poll loop.
        worker._poll_interval = 30  # type: ignore[attr-defined]
        # Note: server_hint_seconds is typed as int on the wire, but
        # _resolve_wait_seconds tolerates any positive int.
        self.assertEqual(WorkerDispatcher._resolve_wait_seconds(worker, 1), 1.0)

    def test_cluster_log_omits_worker_timestamp_when_aligned(self) -> None:
        from mediapipeline.desktop.network.protocol import LogEntryRequest

        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        entry = LogEntryRequest(
            timestamp="2026-05-08T12:00:00-04:00",
            worker_id="w1",
            worker_name="worker-pc",
            role="coordinator",
            level="INFO",
            event="coordinator_started",
            message="boot",
        )
        entry._worker_ts = "2026-05-08T12:00:00-04:00"  # type: ignore[attr-defined]
        line = CoordinatorDispatcher._format_cluster_log_line(dispatcher, entry)
        # Coordinator-emitted entries shouldn't trail with a redundant tag.
        self.assertNotIn("worker_ts=", line)


def _standalone_app_with_records(*sources: str) -> SimpleNamespace:
    return SimpleNamespace(
        resolved=SimpleNamespace(config_data={"NetworkRole": "standalone"}),
        queue_records=[SimpleNamespace(source_path=source) for source in sources],
        _machine_id="standalone-test",
    )


class StandaloneDispatcherTests(unittest.TestCase):
    def test_claim_release_and_done_own_each_record_exactly_once(self) -> None:
        app = _standalone_app_with_records("A.mkv", "B.mkv")
        dispatcher = StandaloneDispatcher(app)

        first = dispatcher.claim_next()
        self.assertIsNotNone(first)
        self.assertEqual([record.source_path for record in app.queue_records], ["B.mkv"])

        dispatcher.release(first)  # type: ignore[arg-type]
        dispatcher.release(first)  # type: ignore[arg-type]
        self.assertEqual([record.source_path for record in app.queue_records], ["A.mkv", "B.mkv"])

        claimed_again = dispatcher.claim_next()
        self.assertIsNotNone(claimed_again)
        dispatcher.mark_done(claimed_again, success=True)  # type: ignore[arg-type]
        dispatcher.release(claimed_again)  # type: ignore[arg-type]
        self.assertEqual([record.source_path for record in app.queue_records], ["B.mkv"])

    def test_concurrent_factory_dispatchers_claim_unique_records(self) -> None:
        app = _standalone_app_with_records("A.mkv", "B.mkv")
        dispatchers = [get_dispatcher(app) for _ in range(8)]
        barrier = threading.Barrier(len(dispatchers))

        def claim(dispatcher: object) -> object:
            barrier.wait()
            return dispatcher.claim_next()  # type: ignore[attr-defined]

        with ThreadPoolExecutor(max_workers=len(dispatchers)) as executor:
            claims = list(executor.map(claim, dispatchers))

        jobs = [job for job in claims if job is not None]
        self.assertEqual(len(jobs), 2)
        self.assertEqual(len({job.job_id for job in jobs}), 2)
        self.assertEqual({job.record.source_path for job in jobs}, {"A.mkv", "B.mkv"})
        self.assertEqual(app.queue_records, [])

    def test_factory_instances_share_reservations_for_release_and_completion(self) -> None:
        app = _standalone_app_with_records("A.mkv")
        claimant = get_dispatcher(app)
        reconciler = get_dispatcher(app)

        first = claimant.claim_next()
        self.assertIsInstance(claimant, StandaloneDispatcher)
        self.assertIsInstance(reconciler, StandaloneDispatcher)
        self.assertIsNotNone(first)

        reconciler.release(first)  # type: ignore[arg-type]
        restored = claimant.claim_next()
        self.assertIsNotNone(restored)
        reconciler.mark_done(restored, success=True)  # type: ignore[arg-type]
        claimant.release(restored)  # type: ignore[arg-type]

        self.assertEqual(app.queue_records, [])


if __name__ == '__main__':
    unittest.main()
