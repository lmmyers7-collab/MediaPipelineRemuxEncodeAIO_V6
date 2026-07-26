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

from mediapipeline.core.network.registry import InFlightRegistry as CoreInFlightRegistry
from mediapipeline.desktop.network.coordinator import CoordinatorDispatcher
from mediapipeline.desktop.network.encode_config_snapshot import snapshot_encode_config
from mediapipeline.desktop.network.failure_policy import source_has_prior_failure
from mediapipeline.desktop.network.path_map import parse_source_path_map
from mediapipeline.desktop.network.protocol import DoneRequest
from mediapipeline.desktop.network.registry import InFlightRegistry


class NetworkInFlightRegistryTests(unittest.TestCase):
    def test_job_scoped_rollback_preserves_unrelated_registry_mutations(self) -> None:
        registry = InFlightRegistry()
        self.assertTrue(
            registry.claim(
                job_id="job-target",
                worker_id="worker-target",
                worker_name="Target Worker",
                source_path=r"C:\Media\target.mkv",
                encode_config={},
            )
        )
        self.assertTrue(
            registry.claim(
                job_id="job-finished",
                worker_id="worker-finished",
                worker_name="Finished Worker",
                source_path=r"C:\Media\finished.mkv",
                encode_config={},
            )
        )
        rollback = registry.rollback_snapshot(
            "job-target",
            transition="complete",
            success=True,
            elapsed_seconds=12.0,
            output_size_bytes=1_073_741_824,
        )

        self.assertIsNotNone(
            registry.complete(
                "job-target",
                "worker-target",
                success=True,
                elapsed_seconds=12.0,
                output_size_bytes=1_073_741_824,
            )
        )
        self.assertIsNotNone(registry.complete("job-finished", "worker-finished", success=True))
        self.assertTrue(
            registry.claim(
                job_id="job-new",
                worker_id="worker-new",
                worker_name="New Worker",
                source_path=r"C:\Media\new.mkv",
                encode_config={},
            )
        )
        with registry._lock:
            registry._late_terminal_reports.append({"job_id": "job-unrelated", "worker_id": "worker-late"})
            registry._reclaimed_source_quarantine[r"c:\media\quarantined.mkv"] = {
                "source_identity": r"c:\media\quarantined.mkv",
                "source_path": r"C:\Media\quarantined.mkv",
                "job_id": "job-quarantined",
            }

        self.assertTrue(registry.restore_rollback_snapshot(rollback))

        with registry._lock:
            self.assertEqual(set(registry._jobs), {"job-target", "job-new"})
            self.assertEqual(registry.session_completed, 1)
            self.assertEqual(registry._worker_stats["worker-target"]["files"], 0)
            self.assertEqual(registry._worker_stats["worker-finished"]["files"], 1)
            self.assertEqual(
                registry._late_terminal_reports,
                [{"job_id": "job-unrelated", "worker_id": "worker-late"}],
            )
            self.assertIn(r"c:\media\quarantined.mkv", registry._reclaimed_source_quarantine)

    def test_failed_completion_rollback_preserves_later_same_worker_success(self) -> None:
        registry = InFlightRegistry()
        for job_id, source_name in (("job-target", "target.mkv"), ("job-finished", "finished.mkv")):
            self.assertTrue(
                registry.claim(
                    job_id=job_id,
                    worker_id="worker-shared",
                    worker_name="Shared Worker",
                    source_path=rf"C:\Media\{source_name}",
                    encode_config={},
                )
            )
        rollback = registry.rollback_snapshot("job-target", transition="complete", success=False)

        registry.complete(
            "job-target",
            "worker-shared",
            success=False,
            reason_code="ENCODE_ERROR",
            reason="target failure",
        )
        registry.complete(
            "job-finished",
            "worker-shared",
            success=True,
            elapsed_seconds=5.0,
            output_size_bytes=1_073_741_824,
        )

        self.assertTrue(registry.restore_rollback_snapshot(rollback))
        with registry._lock:
            self.assertEqual(set(registry._jobs), {"job-target"})
            self.assertEqual(registry.session_completed, 1)
            self.assertEqual(registry.session_failed, 0)
            stats = registry._worker_stats["worker-shared"]
            self.assertEqual(stats["files"], 1)
            self.assertEqual(stats["failure_streak_count"], 0)
            self.assertEqual(stats["last_failure_job_id"], "")
            self.assertNotIn(
                "worker-shared\0c:\\media\\target.mkv",
                registry._failure_ledger,
            )

    def test_job_scoped_rollback_refuses_new_source_owner_without_replacing_it(self) -> None:
        registry = InFlightRegistry()
        self.assertTrue(
            registry.claim(
                job_id="job-target",
                worker_id="worker-target",
                worker_name="Target Worker",
                source_path=r"C:\Media\target.mkv",
                encode_config={},
            )
        )
        rollback = registry.rollback_snapshot("job-target", transition="release")
        self.assertIsNotNone(registry.unclaim("job-target", "worker-target"))
        self.assertTrue(
            registry.claim(
                job_id="job-new-owner",
                worker_id="worker-new",
                worker_name="New Worker",
                source_path=r"C:\Media\target.mkv",
                encode_config={},
            )
        )

        with self.assertLogs("mediapipeline.desktop.network.registry", level="ERROR"):
            self.assertFalse(registry.restore_rollback_snapshot(rollback))
        with registry._lock:
            self.assertEqual(set(registry._jobs), {"job-new-owner"})
            self.assertEqual(registry._claimed_paths[r"c:\media\target.mkv"], "job-new-owner")

    def test_inflight_registry_save_survives_concurrent_saves(self) -> None:
        for label, registry_type in (
            ("core", CoreInFlightRegistry),
            ("desktop", InFlightRegistry),
        ):
            with self.subTest(registry=label), tempfile.TemporaryDirectory() as td:
                path = Path(td) / "inflight_registry.json"
                registry = registry_type()
                errors: list[Exception] = []

                def save_many(
                    active_registry: CoreInFlightRegistry | InFlightRegistry,
                    active_path: Path,
                    active_errors: list[Exception],
                ) -> None:
                    try:
                        for _ in range(20):
                            active_registry.save(active_path)
                    except Exception as exc:
                        active_errors.append(exc)

                threads = [
                    threading.Thread(target=save_many, args=(registry, path, errors))
                    for _ in range(4)
                ]
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
        for label, registry_type, replace_target, logger_name in (
            (
                "core",
                CoreInFlightRegistry,
                "mediapipeline.core.network.registry_persistence.os.replace",
                "mediapipeline.core.network.registry",
            ),
            (
                "desktop",
                InFlightRegistry,
                "mediapipeline.desktop.network.registry_persistence.os.replace",
                "mediapipeline.desktop.network.registry",
            ),
        ):
            with self.subTest(registry=label), tempfile.TemporaryDirectory() as td:
                path = Path(td) / "inflight_registry.json"
                registry = registry_type()

                with (
                    patch(replace_target, side_effect=OSError("replace denied")),
                    patch("pathlib.Path.unlink", side_effect=OSError("cleanup denied")),
                    self.assertLogs(logger_name, level="WARNING") as logs,
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

    def test_inflight_registry_rejects_duplicate_job_id_without_mutating_original(self) -> None:
        registry = InFlightRegistry()

        self.assertTrue(
            registry.claim(
                job_id="job-1",
                worker_id="worker-1",
                worker_name="Worker One",
                source_path=r"C:\Media\first.mkv",
                encode_config={"quality": "first"},
            )
        )
        self.assertFalse(
            registry.claim(
                job_id="job-1",
                worker_id="worker-2",
                worker_name="Worker Two",
                source_path=r"C:\Media\second.mkv",
                encode_config={"quality": "second"},
            )
        )

        rows = registry.snapshot()
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].worker_id, "worker-1")
        self.assertEqual(rows[0].current_file, r"C:\Media\first.mkv")
        self.assertFalse(registry.is_in_flight(r"C:\Media\second.mkv"))

    def test_inflight_registry_normalizes_source_identity_for_claims_and_failures(self) -> None:
        registry = InFlightRegistry()

        self.assertTrue(
            registry.claim(
                job_id="job-1",
                worker_id="worker-1",
                worker_name="Worker",
                source_path=r"C:\Media\Movie.mkv",
                encode_config={},
            )
        )
        self.assertFalse(
            registry.claim(
                job_id="job-2",
                worker_id="worker-2",
                worker_name="Worker Two",
                source_path="c:/media/movie.mkv",
                encode_config={},
            )
        )
        self.assertTrue(registry.is_in_flight("c:/media/movie.mkv"))

        registry.complete(
            "job-1",
            "worker-1",
            success=False,
            reason_code="SOURCE_NOT_FOUND",
            reason="missing",
        )
        blocked = registry.claim_blocked_by_failure(
            worker_id="worker-1",
            source_path="c:/media/movie.mkv",
            max_retries=1,
        )
        self.assertIsNotNone(blocked)

        failure_records = [SimpleNamespace(source_path_text=r"C:\Media\Movie.mkv")]
        self.assertTrue(source_has_prior_failure("c:/media/movie.mkv", failure_records))

    def test_inflight_registry_load_rejects_duplicate_source_identity_variants(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "inflight_registry.json"
            path.write_text(
                json.dumps(
                    {
                        "jobs": [
                            {
                                "job_id": "job-1",
                                "worker_id": "worker-1",
                                "worker_name": "Worker",
                                "source_path": r"C:\Media\Movie.mkv",
                                "claimed_at": "2026-06-15T00:00:00+00:00",
                                "last_heartbeat": "2026-06-15T00:00:00+00:00",
                            },
                            {
                                "job_id": "job-2",
                                "worker_id": "worker-2",
                                "worker_name": "Worker Two",
                                "source_path": "c:/media/movie.mkv",
                                "claimed_at": "2026-06-15T00:00:00+00:00",
                                "last_heartbeat": "2026-06-15T00:00:00+00:00",
                            },
                        ]
                    }
                ),
                encoding="utf-8",
            )
            registry = InFlightRegistry()

            with self.assertLogs("mediapipeline.desktop.network.registry", level="ERROR") as logs:
                loaded = registry.load(path)

        self.assertFalse(loaded)
        self.assertIn("duplicate in-flight source_path", "\n".join(logs.output))

    def test_inflight_registry_persists_reclaim_ledger_for_late_done_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "inflight_registry.json"
            registry = InFlightRegistry()
            self.assertTrue(
                registry.claim(
                    job_id="job-stale",
                    worker_id="worker-1",
                    worker_name="Worker",
                    source_path=r"C:\Media\stale.mkv",
                    encode_config={},
                )
            )
            with registry._lock:
                registry._jobs["job-stale"].last_heartbeat = "2026-01-01T00:00:00+00:00"

            reclaimed = registry.reclaim_stale(0.01)
            self.assertEqual([job.job_id for job in reclaimed], ["job-stale"])
            registry.save(path)

            restored = InFlightRegistry()
            self.assertTrue(restored.load(path))

        ledger = restored.reclaim_ledger_snapshot()
        self.assertEqual(len(ledger), 1)
        self.assertEqual(ledger[0]["job_id"], "job-stale")
        self.assertEqual(ledger[0]["source_path"], r"C:\Media\stale.mkv")

    def test_reclaimed_source_quarantine_blocks_duplicate_claim_until_late_success(self) -> None:
        registry = InFlightRegistry()
        source = r"C:\Media\stale.mkv"
        self.assertTrue(
            registry.claim(
                job_id="job-stale",
                worker_id="worker-1",
                worker_name="Worker",
                source_path=source,
                encode_config={},
            )
        )
        with registry._lock:
            registry._jobs["job-stale"].last_heartbeat = "2026-01-01T00:00:00+00:00"

        reclaimed = registry.reclaim_stale(0.01)
        self.assertEqual([job.job_id for job in reclaimed], ["job-stale"])
        self.assertTrue(registry.is_in_flight(source))
        self.assertFalse(
            registry.claim(
                job_id="job-duplicate",
                worker_id="worker-2",
                worker_name="Worker Two",
                source_path="c:/media/stale.mkv",
                encode_config={},
            )
        )

        report = registry.record_late_terminal_report(
            SimpleNamespace(
                job_id="job-stale",
                worker_id="worker-1",
                success=True,
                output_path=r"C:\Out\stale.mkv",
            )
        )
        self.assertIsNotNone(report)
        self.assertTrue(report["accepted"])
        self.assertEqual(report["authorization_status"], "accepted")
        self.assertTrue(report["removes_queue_record"])
        self.assertTrue(registry.clear_reclaimed_source_quarantine(source))
        with registry._lock:
            registry._recent_completions.clear()

        self.assertFalse(registry.is_in_flight(source))

    def test_retryable_late_failure_keeps_reclaimed_source_quarantined(self) -> None:
        registry = InFlightRegistry()
        source = r"C:\Media\retryable.mkv"
        self.assertTrue(
            registry.claim(
                job_id="job-stale",
                worker_id="worker-1",
                worker_name="Worker",
                source_path=source,
                encode_config={},
            )
        )
        with registry._lock:
            registry._jobs["job-stale"].last_heartbeat = "2026-01-01T00:00:00+00:00"

        registry.reclaim_stale(0.01)
        report = registry.record_late_terminal_report(
            SimpleNamespace(
                job_id="job-stale",
                worker_id="worker-1",
                success=False,
                queue_terminal=False,
                retry_on_failure=True,
                reason_code="ENCODE_ERROR",
                reason="worker lost coordinator",
            )
        )
        self.assertIsNotNone(report)
        self.assertTrue(report["accepted"])
        self.assertEqual(report["authorization_status"], "accepted")
        self.assertFalse(report["removes_queue_record"])
        with registry._lock:
            registry._recent_completions.clear()

        self.assertTrue(registry.is_in_flight("c:/media/retryable.mkv"))
        stats = registry.reclaimed_source_quarantine_stats()
        self.assertEqual(stats["count"], 1)

    def test_late_terminal_report_rejects_worker_that_did_not_own_reclaimed_job(self) -> None:
        registry = InFlightRegistry()
        source = r"C:\Media\owner-bound.mkv"
        self.assertTrue(
            registry.claim(
                job_id="job-owner-bound",
                worker_id="worker-owner",
                worker_name="Owner Worker",
                source_path=source,
                encode_config={},
            )
        )
        with registry._lock:
            registry._jobs["job-owner-bound"].last_heartbeat = "2026-01-01T00:00:00+00:00"
        self.assertEqual(
            [job.job_id for job in registry.reclaim_stale(0.01)],
            ["job-owner-bound"],
        )

        report = registry.record_late_terminal_report(
            SimpleNamespace(
                job_id="job-owner-bound",
                worker_id="worker-foreign",
                success=True,
                queue_terminal=True,
            )
        )

        self.assertIsNotNone(report)
        self.assertFalse(report["accepted"])
        self.assertEqual(report["authorization_status"], "rejected_owner_mismatch")
        self.assertEqual(report["reclaimed_worker_id"], "worker-owner")
        self.assertFalse(report["removes_queue_record"])
        self.assertEqual(registry.late_terminal_reports_snapshot(), [report])
        self.assertTrue(registry.is_in_flight(source))
        self.assertEqual(registry.reclaimed_source_quarantine_stats()["count"], 1)

    def test_late_terminal_report_carries_server_created_rerun_identity(self) -> None:
        registry = InFlightRegistry()
        source = r"C:\Media\rerun.mkv"
        self.assertTrue(
            registry.claim(
                job_id="job-rerun",
                worker_id="worker-owner",
                worker_name="Owner Worker",
                source_path=source,
                encode_config={},
                job_kind="csv_rerun_row",
                claim_metadata={
                    "job_kind": "csv_rerun_row",
                    "rerun_batch_id": "batch-1",
                    "rerun_row_key": "row-1",
                },
            )
        )
        with registry._lock:
            registry._jobs["job-rerun"].last_heartbeat = "2026-01-01T00:00:00+00:00"
        registry.reclaim_stale(0.01)

        report = registry.record_late_terminal_report(
            SimpleNamespace(job_id="job-rerun", worker_id="worker-owner", success=True)
        )

        self.assertIsNotNone(report)
        self.assertEqual(report["job_kind"], "csv_rerun_row")
        self.assertEqual(report["rerun_batch_id"], "batch-1")
        self.assertEqual(report["rerun_row_key"], "row-1")

    def test_failure_ledger_is_capped_and_persists_bounded_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "inflight_registry.json"
            registry = InFlightRegistry()
            registry._RECENT_COMPLETION_TTL_SECONDS = 0.0

            for index in range(5005):
                source = rf"C:\Media\failure-{index}.mkv"
                job_id = f"job-{index}"
                self.assertTrue(
                    registry.claim(
                        job_id=job_id,
                        worker_id="worker-1",
                        worker_name="Worker",
                        source_path=source,
                        encode_config={},
                    )
                )
                registry.complete(
                    job_id,
                    "worker-1",
                    success=False,
                    reason_code="SOURCE_NOT_FOUND",
                    reason="missing",
                )

            self.assertEqual(registry.failure_ledger_stats()["count"], 5000)
            self.assertIsNone(
                registry.claim_blocked_by_failure(
                    worker_id="worker-1",
                    source_path=r"C:\Media\failure-0.mkv",
                    max_retries=1,
                )
            )
            self.assertIsNotNone(
                registry.claim_blocked_by_failure(
                    worker_id="worker-1",
                    source_path=r"C:\Media\failure-5004.mkv",
                    max_retries=1,
                )
            )
            registry.save(path)

            restored = InFlightRegistry()
            self.assertTrue(restored.load(path))

        self.assertEqual(restored.failure_ledger_stats(), {"count": 5000, "max_entries": 5000})

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
