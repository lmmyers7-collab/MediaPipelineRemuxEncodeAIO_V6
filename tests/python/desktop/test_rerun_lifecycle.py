from __future__ import annotations

import json
import os
import tempfile
import threading
import unittest
from pathlib import Path
from unittest import mock

from mediapipeline.core.processes.rerun_lifecycle import (
    create_rerun_enrollment,
    finalize_rerun_enrollment_after_exit,
    new_rerun_correlation,
    read_rerun_enrollment,
    record_rerun_spawn_transition_ambiguity,
    record_rerun_spawn_transition_failure,
    reconcile_local_rerun_enrollments,
    rerun_correlation_evidence,
    rerun_lifecycle_counts,
    rerun_execution_manifest_has_durable_exit_state,
    transition_rerun_enrollment,
)
from mediapipeline.core.processes.rerun_results import rerun_results_payload
from tests.python.desktop.application_facade_test_support import _resolved


class RerunLifecycleTests(unittest.TestCase):
    @staticmethod
    def _enrollment(root: Path):
        resolved = _resolved(root)
        resolved.local_base = root / "LocalBase"
        resolved.state_root = resolved.local_base / "State"
        csv_path = root / "rerun.csv"
        source = root / "Media" / "Movie.mkv"
        source.parent.mkdir(parents=True)
        source.write_bytes(b"media")
        csv_path.write_text(f"enabled,source_path\ntrue,{source}\n", encoding="utf-8")
        correlation = new_rerun_correlation(resolved, command_id="command-test")
        create_rerun_enrollment(
            resolved,
            correlation=correlation,
            csv_path=csv_path,
            source_csv_path=csv_path,
            dry_run=False,
            lifecycle={},
        )
        transition_rerun_enrollment(correlation.enrollment_path, "process_spawned", expected_states={"accepted"})
        return correlation

    def test_exit_finalizer_preserves_newer_enrollment_and_execution_manifest_states(self) -> None:
        preserved_states = ("waiting_for_source", "retry_scheduled", "retry_exhausted", "review", "completed")
        for state in preserved_states:
            with self.subTest(state=state), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root)
                correlation = self._enrollment(root)
                transition_rerun_enrollment(correlation.enrollment_path, state, expected_states={"process_spawned"})

                finalize_rerun_enrollment_after_exit(
                    {"enrollment_path": str(correlation.enrollment_path), "manifest_path": str(correlation.manifest_path)},
                    9,
                )

                enrollment = read_rerun_enrollment(correlation.enrollment_path)
                self.assertIsNotNone(enrollment)
                self.assertEqual(enrollment["status"], state)

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            correlation = self._enrollment(root)
            correlation.manifest_path.parent.mkdir(parents=True)
            correlation.manifest_path.write_text(
                json.dumps({"batch_id": correlation.batch_id, "status": "retry_scheduled"}),
                encoding="utf-8",
            )

            finalize_rerun_enrollment_after_exit(
                {"enrollment_path": str(correlation.enrollment_path), "manifest_path": str(correlation.manifest_path)},
                9,
            )

            enrollment = read_rerun_enrollment(correlation.enrollment_path)
            self.assertIsNotNone(enrollment)
            self.assertEqual(enrollment["status"], "process_spawned")
            manifest = json.loads(correlation.manifest_path.read_text(encoding="utf-8"))
            self.assertEqual(manifest["status"], "retry_scheduled")

    def test_nonzero_exit_before_manifest_terminalizes_enrollment_with_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            correlation = self._enrollment(root)
            active_jobs_path = root / "LocalBase" / "State" / "ActiveJobs" / f"{correlation.launch_id}.json"
            stdout_log = root / "RunLogs" / "rerun.stdout.log"
            stderr_log = root / "RunLogs" / "rerun.stderr.log"

            finalize_rerun_enrollment_after_exit(
                {
                    "enrollment_path": str(correlation.enrollment_path),
                    "manifest_path": str(correlation.manifest_path),
                    "active_jobs_path": str(active_jobs_path),
                    "stdout_log": str(stdout_log),
                    "stderr_log": str(stderr_log),
                },
                17,
            )

            enrollment = read_rerun_enrollment(correlation.enrollment_path)
            self.assertIsNotNone(enrollment)
            self.assertEqual(enrollment["status"], "failed_before_manifest")
            self.assertEqual(enrollment["return_code"], 17)
            self.assertEqual(enrollment["evidence_links"]["active_jobs"], str(active_jobs_path))
            self.assertEqual(enrollment["evidence_links"]["stdout_log"], str(stdout_log))
            self.assertEqual(enrollment["evidence_links"]["stderr_log"], str(stderr_log))
            self.assertEqual(enrollment["rows"][0]["status"], "failed_before_manifest")

    def test_verified_exit_terminalizes_spawn_transition_ambiguity(self) -> None:
        for manifest_observed, expected_state in ((False, "failed_before_manifest"), (True, "failed")):
            with self.subTest(manifest_observed=manifest_observed), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root)
                correlation = self._enrollment(root)
                record_rerun_spawn_transition_ambiguity(
                    correlation.enrollment_path,
                    reason="Child stop could not be verified.",
                    pid=24682,
                )
                if manifest_observed:
                    correlation.manifest_path.parent.mkdir(parents=True)
                    correlation.manifest_path.write_text(
                        json.dumps({"batch_id": correlation.batch_id, "status": "manifest_created"}),
                        encoding="utf-8",
                    )

                finalize_rerun_enrollment_after_exit(
                    {
                        "enrollment_path": str(correlation.enrollment_path),
                        "manifest_path": str(correlation.manifest_path),
                    },
                    17,
                )

                enrollment = read_rerun_enrollment(correlation.enrollment_path)
                self.assertIsNotNone(enrollment)
                self.assertEqual(enrollment["status"], expected_state)
                self.assertTrue(enrollment["process_exit_verified"])
                self.assertFalse(enrollment["duplicate_launch_blocked"])

    def test_verified_spawn_transition_failure_persists_supersession_proof(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            correlation = self._enrollment(Path(raw_root))

            record_rerun_spawn_transition_failure(
                correlation.enrollment_path,
                reason="Tree cleanup and child exit were verified.",
            )
            enrollment = read_rerun_enrollment(correlation.enrollment_path)

        self.assertIsNotNone(enrollment)
        self.assertEqual(enrollment["status"], "failed_before_manifest")
        self.assertTrue(enrollment["process_exit_verified"])
        self.assertFalse(enrollment["duplicate_launch_blocked"])

    def test_ambiguity_record_cannot_overwrite_concurrent_terminal_exit(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            correlation = self._enrollment(root)
            original_write = __import__(
                "mediapipeline.core.processes.rerun_lifecycle",
                fromlist=["_write_payload"],
            )._write_payload
            ambiguity_write_reached = threading.Event()
            release_ambiguity_write = threading.Event()
            terminal_finished = threading.Event()

            def coordinated_write(path: Path, payload: dict[str, object]) -> None:
                if (
                    str(payload.get("status") or "") == "spawn_transition_ambiguous"
                    and payload.get("process_exit_verified") is False
                ):
                    ambiguity_write_reached.set()
                    release_ambiguity_write.wait(timeout=1)
                original_write(path, payload)

            def record_ambiguity() -> None:
                record_rerun_spawn_transition_ambiguity(
                    correlation.enrollment_path,
                    reason="Child stop could not be verified.",
                    pid=24682,
                )

            def finalize_exit() -> None:
                finalize_rerun_enrollment_after_exit(
                    {
                        "enrollment_path": str(correlation.enrollment_path),
                        "manifest_path": str(correlation.manifest_path),
                    },
                    17,
                )
                terminal_finished.set()

            with mock.patch(
                "mediapipeline.core.processes.rerun_lifecycle._write_payload",
                side_effect=coordinated_write,
            ):
                ambiguity = threading.Thread(target=record_ambiguity)
                ambiguity.start()
                self.assertTrue(ambiguity_write_reached.wait(timeout=1))
                terminal = threading.Thread(target=finalize_exit)
                terminal.start()
                terminal_finished.wait(timeout=0.2)
                release_ambiguity_write.set()
                ambiguity.join(timeout=2)
                terminal.join(timeout=2)

            self.assertFalse(ambiguity.is_alive())
            self.assertFalse(terminal.is_alive())
            enrollment = read_rerun_enrollment(correlation.enrollment_path)
            self.assertIsNotNone(enrollment)
            self.assertEqual(enrollment["status"], "failed_before_manifest")
            self.assertTrue(enrollment["process_exit_verified"])

    def test_exit_after_incomplete_manifest_terminalizes_enrollment_and_results_use_terminal_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            correlation = self._enrollment(root)
            enrollment = read_rerun_enrollment(correlation.enrollment_path)
            self.assertIsNotNone(enrollment)
            correlation.manifest_path.parent.mkdir(parents=True)
            correlation.manifest_path.write_text(
                json.dumps(
                    {
                        "batch_id": correlation.batch_id,
                        "command_id": correlation.command_id,
                        "launch_id": correlation.launch_id,
                        "enrollment_path": str(correlation.enrollment_path),
                        "status": "manifest_created",
                        "current_phase": "manifest_created",
                        "rows": [
                            {
                                "source_path": enrollment["rows"][0]["source_path"],
                                "status": "accepted",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )

            finalize_rerun_enrollment_after_exit(
                {
                    "enrollment_path": str(correlation.enrollment_path),
                    "manifest_path": str(correlation.manifest_path),
                },
                23,
            )

            terminal_enrollment = read_rerun_enrollment(correlation.enrollment_path)
            self.assertIsNotNone(terminal_enrollment)
            self.assertEqual(terminal_enrollment["status"], "failed")
            self.assertEqual(terminal_enrollment["reason_code"], "rerun_process_exit_before_terminal_manifest")
            self.assertEqual(terminal_enrollment["evidence_links"]["manifest"], str(correlation.manifest_path))

            restarted_resolved = _resolved(root)
            restarted_resolved.local_base = root / "LocalBase"
            restarted_resolved.state_root = restarted_resolved.local_base / "State"
            payload = rerun_results_payload(restarted_resolved)

        manifest = payload["manifests"][0]
        self.assertEqual(manifest["status"], "failed")
        self.assertEqual(manifest["execution_manifest_status"], "manifest_created")
        self.assertEqual(
            manifest["evidence_authority"],
            "backend_enrollment_terminal_over_incomplete_execution_manifest",
        )
        self.assertEqual(manifest["rows"][0]["queue_status"], "failed")
        self.assertTrue(manifest["rows"][0]["is_terminal"])

    def test_lifecycle_counts_cover_the_backend_authored_operator_buckets(self) -> None:
        counts = rerun_lifecycle_counts(
            [
                {"lifecycle_state": "accepted"},
                {"lifecycle_state": "invalid"},
                {"lifecycle_state": "waiting_for_source"},
                {"lifecycle_state": "retry_scheduled"},
                {"lifecycle_state": "staged"},
                {"lifecycle_state": "processing"},
                {"lifecycle_state": "completed"},
                {"lifecycle_state": "failed"},
                {"lifecycle_state": "review_workspace"},
                {"lifecycle_state": "pending_publish"},
            ]
        )
        self.assertEqual(
            counts,
            {
                "total": 10,
                "executable": 1,
                "blocked": 1,
                "waiting": 2,
                "retrying": 1,
                "staged": 1,
                "active": 1,
                "completed": 1,
                "failed": 1,
                "review": 1,
                "pending_publish": 1,
                "terminal": 4,
            },
        )

    def test_terminal_lifecycle_wrappers_use_semantic_row_status_for_counts_and_exit_proof(self) -> None:
        rows = [
            {"lifecycle_state": "terminal", "status": "published_replace_final"},
            {"lifecycle_state": "terminal", "status": "review_workspace"},
            {"lifecycle_state": "terminal", "status": "pending_publish"},
            {"lifecycle_state": "terminal", "status": "failed"},
        ]

        counts = rerun_lifecycle_counts(rows)

        self.assertEqual(counts["total"], 4)
        self.assertEqual(counts["completed"], 1)
        self.assertEqual(counts["review"], 1)
        self.assertEqual(counts["pending_publish"], 1)
        self.assertEqual(counts["failed"], 1)
        self.assertEqual(counts["terminal"], 4)
        self.assertTrue(
            rerun_execution_manifest_has_durable_exit_state(
                {
                    "lifecycle_state": "terminal",
                    "status": "completed_with_failed_rows",
                    "rows": rows,
                }
            )
        )

    def test_spawn_transition_ambiguity_counts_as_nonterminal_blocked_active_work(self) -> None:
        counts = rerun_lifecycle_counts([{"lifecycle_state": "spawn_transition_ambiguous"}])

        self.assertEqual(counts["total"], 1)
        self.assertEqual(counts["blocked"], 1)
        self.assertEqual(counts["active"], 1)
        self.assertEqual(counts["terminal"], 0)

    def test_enrollment_and_results_projection_survive_backend_restart(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            correlation = self._enrollment(root)
            transition_rerun_enrollment(
                correlation.enrollment_path,
                "waiting_for_source",
                expected_states={"process_spawned"},
                reason_code="source_location_unavailable",
                reason="Configured source root is temporarily unavailable.",
            )
            enrollment = read_rerun_enrollment(correlation.enrollment_path)
            self.assertIsNotNone(enrollment)
            enrollment["rows"][0].update(
                {
                    "status": "waiting_for_source",
                    "lifecycle_state": "waiting_for_source",
                    "reason_code": "source_location_unavailable",
                    "last_transition_at": enrollment["last_transition_at"],
                }
            )
            correlation.enrollment_path.write_text(json.dumps(enrollment), encoding="utf-8")

            restarted_resolved = _resolved(root)
            restarted_resolved.local_base = root / "LocalBase"
            restarted_resolved.state_root = restarted_resolved.local_base / "State"
            payload = rerun_results_payload(restarted_resolved)

        self.assertEqual(len(payload["manifests"]), 1)
        manifest = payload["manifests"][0]
        self.assertFalse(manifest["manifest_available"])
        self.assertEqual(manifest["evidence_authority"], "backend_enrollment")
        self.assertEqual(manifest["command_id"], correlation.command_id)
        self.assertEqual(manifest["launch_id"], correlation.launch_id)
        self.assertEqual(manifest["batch_id"], correlation.batch_id)
        self.assertEqual(manifest["status"], "waiting_for_source")
        self.assertEqual(manifest["rows"][0]["lifecycle_state"], "waiting_for_source")
        self.assertEqual(manifest["lifecycle_counts"]["waiting"], 1)

    def test_transition_serialization_prevents_stale_spawn_state_from_overwriting_terminal_exit(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            correlation = self._enrollment(Path(raw_root))
            transition_rerun_enrollment(
                correlation.enrollment_path,
                "accepted",
                expected_states={"process_spawned"},
            )
            original_read = read_rerun_enrollment
            spawn_read_started = threading.Event()
            terminal_transition_finished = threading.Event()

            def coordinated_read(path: Path):
                payload = original_read(path)
                if threading.current_thread().name == "stale-spawn-transition":
                    spawn_read_started.set()
                    terminal_transition_finished.wait(timeout=0.25)
                return payload

            def apply_spawn_transition() -> None:
                transition_rerun_enrollment(
                    correlation.enrollment_path,
                    "process_spawned",
                    expected_states={"accepted"},
                )

            def apply_terminal_transition() -> None:
                transition_rerun_enrollment(
                    correlation.enrollment_path,
                    "failed_before_manifest",
                    expected_states={"accepted", "process_spawned"},
                    reason_code="rerun_process_exit_nonzero",
                    reason="Child exited before manifest creation.",
                )
                terminal_transition_finished.set()

            with mock.patch(
                "mediapipeline.core.processes.rerun_lifecycle.read_rerun_enrollment",
                side_effect=coordinated_read,
            ):
                stale_spawn = threading.Thread(target=apply_spawn_transition, name="stale-spawn-transition")
                stale_spawn.start()
                self.assertTrue(spawn_read_started.wait(timeout=1))
                terminal_exit = threading.Thread(target=apply_terminal_transition, name="terminal-exit-transition")
                terminal_exit.start()
                stale_spawn.join(timeout=2)
                terminal_exit.join(timeout=2)

            self.assertFalse(stale_spawn.is_alive())
            self.assertFalse(terminal_exit.is_alive())
            enrollment = read_rerun_enrollment(correlation.enrollment_path)
            self.assertIsNotNone(enrollment)
            self.assertEqual(enrollment["status"], "failed_before_manifest")

    def test_premanifest_enrollment_persists_operator_evidence_for_each_transition(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            source = root / "Media" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path\ntrue,{source}\n", encoding="utf-8")
            correlation = new_rerun_correlation(resolved, command_id="command-evidence")

            create_rerun_enrollment(
                resolved,
                correlation=correlation,
                csv_path=csv_path,
                source_csv_path=csv_path,
                dry_run=False,
                lifecycle={},
            )
            accepted = read_rerun_enrollment(correlation.enrollment_path)
            self.assertIsNotNone(accepted)
            self.assertEqual(accepted["rows"][0]["lifecycle_state"], "accepted")
            for timeline in (accepted["timeline"], accepted["rows"][0]["timeline"]):
                self.assertEqual([entry["state"] for entry in timeline], ["requested", "accepted"])
                self.assertEqual([entry["sequence"] for entry in timeline], [1, 2])
                entry = timeline[-1]
                self.assertEqual(entry["what"], "The CSV rerun request is durably enrolled.")
                self.assertTrue(entry["why"])
                self.assertTrue(entry["when"])
                self.assertTrue(entry["next"])
            self.assertTrue(accepted["rows"][0]["reason"])
            self.assertTrue(accepted["rows"][0]["automatic_next_action"])
            self.assertFalse(accepted["rows"][0]["operator_action_required"])

            transition_rerun_enrollment(
                correlation.enrollment_path,
                "process_spawned",
                expected_states={"accepted"},
                pid=90210,
            )
            spawned = read_rerun_enrollment(correlation.enrollment_path)
            self.assertIsNotNone(spawned)
            self.assertTrue(spawned["created_at"])
            self.assertTrue(spawned["started_at"])
            self.assertEqual(spawned["rows"][0]["lifecycle_state"], "process_spawned")
            self.assertEqual(spawned["rows"][0]["started_at"], spawned["started_at"])
            self.assertEqual(
                spawned["rows"][0]["timeline"][-1]["what"],
                "The dedicated CSV rerun process has spawned.",
            )
            self.assertTrue(spawned["rows"][0]["timeline"][-1]["next"])
            self.assertEqual([entry["sequence"] for entry in spawned["timeline"]], [1, 2, 3])
            self.assertEqual([entry["sequence"] for entry in spawned["rows"][0]["timeline"]], [1, 2, 3])

            transition_rerun_enrollment(
                correlation.enrollment_path,
                "failed_before_manifest",
                expected_states={"process_spawned"},
                reason_code="rerun_process_exit_nonzero",
                reason="Child exited before manifest creation.",
            )
            restarted_resolved = _resolved(root)
            restarted_resolved.local_base = root / "LocalBase"
            restarted_resolved.state_root = restarted_resolved.local_base / "State"
            terminal = read_rerun_enrollment(correlation.enrollment_path)
            self.assertIsNotNone(terminal)
            self.assertEqual([entry["sequence"] for entry in terminal["timeline"]], [1, 2, 3, 4])
            self.assertEqual([entry["sequence"] for entry in terminal["rows"][0]["timeline"]], [1, 2, 3, 4])
            projected = rerun_results_payload(restarted_resolved)["manifests"][0]["rows"][0]

        self.assertEqual(projected["lifecycle_state"], "failed_before_manifest")
        self.assertEqual(
            projected["lifecycle_evidence"]["what"],
            "The CSV rerun process ended before row execution evidence was created.",
        )
        self.assertEqual(projected["lifecycle_evidence"]["why"], "Child exited before manifest creation.")
        self.assertTrue(projected["lifecycle_evidence"]["when"])
        self.assertTrue(projected["lifecycle_evidence"]["next"])
        self.assertTrue(projected["operator_action_required"])
        self.assertTrue(projected["available_operator_action"])

    def test_enrollment_preserves_disabled_csv_rows_and_initial_counts(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            enabled_source = root / "Media" / "Enabled.mkv"
            disabled_source = root / "Media" / "Disabled.mkv"
            enabled_source.parent.mkdir(parents=True)
            enabled_source.write_bytes(b"enabled")
            disabled_source.write_bytes(b"disabled")
            csv_path = root / "rerun.csv"
            csv_path.write_text(
                "enabled,source_path\n"
                f"true,{enabled_source}\n"
                f"false,{disabled_source}\n",
                encoding="utf-8",
            )
            correlation = new_rerun_correlation(resolved, command_id="command-disabled")
            enrollment = create_rerun_enrollment(
                resolved,
                correlation=correlation,
                csv_path=csv_path,
                source_csv_path=csv_path,
                dry_run=False,
                lifecycle={},
            )

            self.assertEqual([row["lifecycle_state"] for row in enrollment["rows"]], ["accepted", "disabled"])
            self.assertEqual(enrollment["lifecycle_counts"]["total"], 2)
            self.assertEqual(enrollment["lifecycle_counts"]["executable"], 1)
            self.assertEqual(enrollment["lifecycle_counts"]["terminal"], 1)
            payload = rerun_results_payload(resolved)

        manifest = payload["manifests"][0]
        self.assertEqual(manifest["lifecycle_counts"]["total"], 2)
        self.assertEqual(manifest["lifecycle_counts"]["executable"], 1)
        self.assertEqual(manifest["lifecycle_counts"]["terminal"], 1)
        disabled = manifest["rows"][1]
        self.assertEqual(disabled["lifecycle_state"], "disabled")
        self.assertEqual(disabled["queue_status"], "skipped")
        self.assertTrue(disabled["is_terminal"])
        self.assertTrue(disabled["lifecycle_evidence"]["why"])
        self.assertTrue(disabled["lifecycle_evidence"]["next"])

    def test_new_enrollment_is_not_hidden_by_old_execution_manifests_at_result_limit(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            manifest_root = resolved.local_base / "RerunManifests"
            manifest_root.mkdir(parents=True)
            old_manifest = manifest_root / "old-complete.json"
            old_manifest.write_text(
                json.dumps(
                    {
                        "batch_id": "old-complete",
                        "status": "completed",
                        "rows": [{"status": "completed", "source_path": str(root / "Old.mkv")}],
                    }
                ),
                encoding="utf-8",
            )
            os.utime(old_manifest, (1, 1))
            correlation = self._enrollment(root)

            payload = rerun_results_payload(resolved, limit=1)

        self.assertEqual(len(payload["manifests"]), 1)
        self.assertEqual(payload["manifests"][0]["batch_id"], correlation.batch_id)
        self.assertFalse(payload["manifests"][0]["manifest_available"])

    def test_startup_reconciliation_terminalizes_orphaned_premanifest_enrollment_without_replay(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            correlation = self._enrollment(root)
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            resolved.active_jobs_path = resolved.state_root / "ActiveJobs"
            resolved.active_jobs_path.mkdir(parents=True)
            active_job_path = resolved.active_jobs_path / f"{correlation.launch_id}.json"
            active_job_path.write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": correlation.launch_id,
                        "job_kind": "rerun_csv",
                        "mode": "rerun_csv",
                        "status": "orphaned",
                        "pid": 90210,
                        "stdout_log": str(root / "rerun.stdout.log"),
                        "stderr_log": str(root / "rerun.stderr.log"),
                        "metadata": {
                            "command_id": correlation.command_id,
                            "batch_id": correlation.batch_id,
                            "enrollment_path": str(correlation.enrollment_path),
                            "manifest_path": str(correlation.manifest_path),
                        },
                    }
                ),
                encoding="utf-8",
            )

            summary = reconcile_local_rerun_enrollments(resolved, pid_is_alive=lambda _pid: False)
            terminal = read_rerun_enrollment(correlation.enrollment_path)
            projected_summary = rerun_results_payload(resolved)["startup_reconciliation"]
            summary_persisted = Path(summary["summary_path"]).is_file()
            repeated = reconcile_local_rerun_enrollments(resolved, pid_is_alive=lambda _pid: False)
            terminal_after_repeat = read_rerun_enrollment(correlation.enrollment_path)

        self.assertIsNotNone(terminal)
        self.assertEqual(summary["terminalized_count"], 1)
        self.assertEqual(summary["replayed_count"], 0)
        self.assertTrue(summary_persisted)
        self.assertEqual(projected_summary["terminalized_count"], 1)
        self.assertEqual(projected_summary["replayed_count"], 0)
        self.assertEqual(terminal["status"], "failed_before_manifest")
        self.assertEqual(terminal["reason_code"], "rerun_startup_child_exit_before_manifest")
        self.assertEqual(terminal["evidence_links"]["active_jobs"], str(active_job_path))
        self.assertEqual(terminal["evidence_links"]["stdout_log"], str(root / "rerun.stdout.log"))
        self.assertIn("orphaned", terminal["reason"])
        self.assertTrue(terminal["process_exit_verified"])
        self.assertFalse(terminal["duplicate_launch_blocked"])
        self.assertEqual(repeated["terminalized_count"], 0)
        self.assertEqual(terminal_after_repeat["transition_sequence"], terminal["transition_sequence"])

    def test_startup_reconciliation_without_child_evidence_preserves_duplicate_block(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            correlation = self._enrollment(root)
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            resolved.active_jobs_path = resolved.state_root / "ActiveJobs"

            summary = reconcile_local_rerun_enrollments(resolved, pid_is_alive=lambda _pid: None)
            enrollment = read_rerun_enrollment(correlation.enrollment_path)

        self.assertEqual(summary["terminalized_count"], 0)
        self.assertEqual(summary["ambiguous_count"], 1)
        self.assertIsNotNone(enrollment)
        self.assertEqual(enrollment["status"], "spawn_transition_ambiguous")
        self.assertFalse(enrollment["process_exit_verified"])
        self.assertTrue(enrollment["duplicate_launch_blocked"])

    def test_startup_reconciliation_preserves_alive_child_and_newer_durable_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            correlation = self._enrollment(root)
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            resolved.active_jobs_path = resolved.state_root / "ActiveJobs"
            resolved.active_jobs_path.mkdir(parents=True)
            active_job_path = resolved.active_jobs_path / f"{correlation.launch_id}.json"
            active_job = {
                "schema_version": "desktop_active_job.v1",
                "launch_id": correlation.launch_id,
                "job_kind": "rerun_csv",
                "mode": "rerun_csv",
                "status": "active",
                "pid": 90210,
                "metadata": {
                    "command_id": correlation.command_id,
                    "batch_id": correlation.batch_id,
                    "enrollment_path": str(correlation.enrollment_path),
                    "manifest_path": str(correlation.manifest_path),
                },
            }
            active_job_path.write_text(json.dumps(active_job), encoding="utf-8")

            alive_summary = reconcile_local_rerun_enrollments(resolved, pid_is_alive=lambda _pid: True)
            alive_enrollment = read_rerun_enrollment(correlation.enrollment_path)
            correlation.manifest_path.parent.mkdir(parents=True)
            correlation.manifest_path.write_text(
                json.dumps(
                    {
                        "batch_id": correlation.batch_id,
                        "command_id": correlation.command_id,
                        "launch_id": correlation.launch_id,
                        "enrollment_path": str(correlation.enrollment_path),
                        "status": "retry_scheduled",
                        "last_transition_at": "2099-01-01T00:00:00Z",
                        "rows": [{"status": "retry_scheduled", "source_path": str(root / "Media" / "Movie.mkv")}],
                    }
                ),
                encoding="utf-8",
            )
            active_job["status"] = "orphaned"
            active_job_path.write_text(json.dumps(active_job), encoding="utf-8")

            manifest_summary = reconcile_local_rerun_enrollments(resolved, pid_is_alive=lambda _pid: False)
            manifest_preserved_enrollment = read_rerun_enrollment(correlation.enrollment_path)

        self.assertEqual(alive_summary["alive_count"], 1)
        self.assertEqual(alive_enrollment["status"], "process_spawned")
        self.assertEqual(manifest_summary["durable_manifest_count"], 1)
        self.assertEqual(manifest_summary["terminalized_count"], 0)
        self.assertNotIn(manifest_preserved_enrollment["status"], {"failed", "failed_before_manifest"})

    def test_startup_reconciliation_rejects_missing_or_mismatched_manifest_correlation(self) -> None:
        for defect in ("missing_launch_id", "mismatched_command_id", "missing_enrollment_path"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root)
                correlation = self._enrollment(root)
                resolved = _resolved(root)
                resolved.local_base = root / "LocalBase"
                resolved.state_root = resolved.local_base / "State"
                resolved.active_jobs_path = resolved.state_root / "ActiveJobs"
                resolved.active_jobs_path.mkdir(parents=True)
                active_job_path = resolved.active_jobs_path / f"{correlation.launch_id}.json"
                active_job_path.write_text(
                    json.dumps(
                        {
                            "launch_id": correlation.launch_id,
                            "job_kind": "rerun_csv",
                            "status": "orphaned",
                            "pid": 24682,
                            "metadata": {
                                "command_id": correlation.command_id,
                                "batch_id": correlation.batch_id,
                                "enrollment_path": str(correlation.enrollment_path),
                                "manifest_path": str(correlation.manifest_path),
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                manifest = {
                    "batch_id": correlation.batch_id,
                    "command_id": correlation.command_id,
                    "launch_id": correlation.launch_id,
                    "enrollment_path": str(correlation.enrollment_path),
                    "status": "completed",
                    "rows": [{"status": "completed"}],
                }
                if defect == "missing_launch_id":
                    manifest.pop("launch_id")
                elif defect == "mismatched_command_id":
                    manifest["command_id"] = "different-command"
                else:
                    manifest.pop("enrollment_path")
                correlation.manifest_path.parent.mkdir(parents=True)
                correlation.manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

                summary = reconcile_local_rerun_enrollments(
                    resolved,
                    pid_is_alive=lambda _pid: False,
                )
                enrollment = read_rerun_enrollment(correlation.enrollment_path)

            self.assertEqual(summary["durable_manifest_count"], 0)
            self.assertEqual(summary["terminalized_count"], 1)
            self.assertEqual(enrollment["status"], "failed")

    def test_startup_reconciliation_checks_kill_degraded_pid_before_preserving(self) -> None:
        for alive in (True, False):
            with self.subTest(alive=alive), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root)
                correlation = self._enrollment(root)
                resolved = _resolved(root)
                resolved.local_base = root / "LocalBase"
                resolved.state_root = resolved.local_base / "State"
                resolved.active_jobs_path = resolved.state_root / "ActiveJobs"
                resolved.active_jobs_path.mkdir(parents=True)
                (resolved.active_jobs_path / f"{correlation.launch_id}.json").write_text(
                    json.dumps(
                        {
                            "schema_version": "desktop_active_job.v1",
                            "launch_id": correlation.launch_id,
                            "job_kind": "rerun_csv",
                            "status": "kill_degraded",
                            "pid": 24682,
                            "metadata": {
                                "command_id": correlation.command_id,
                                "batch_id": correlation.batch_id,
                                "enrollment_path": str(correlation.enrollment_path),
                                "manifest_path": str(correlation.manifest_path),
                            },
                        }
                    ),
                    encoding="utf-8",
                )

                summary = reconcile_local_rerun_enrollments(
                    resolved,
                    pid_is_alive=lambda _pid, result=alive: result,
                )
                enrollment = read_rerun_enrollment(correlation.enrollment_path)

            self.assertIsNotNone(enrollment)
            if alive:
                self.assertEqual(summary["alive_count"], 1)
                self.assertEqual(enrollment["status"], "process_spawned")
            else:
                self.assertEqual(summary["terminalized_count"], 1)
                self.assertEqual(enrollment["status"], "failed_before_manifest")
                self.assertIn("kill_degraded", enrollment["reason"])

    def test_active_jobs_correlation_rejects_missing_or_mismatched_command_and_paths(self) -> None:
        for defect in ("missing_command_id", "mismatched_command_id", "missing_manifest_path"):
            with self.subTest(defect=defect), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root)
                correlation = self._enrollment(root)
                resolved = _resolved(root)
                resolved.local_base = root / "LocalBase"
                resolved.state_root = resolved.local_base / "State"
                resolved.active_jobs_path = resolved.state_root / "ActiveJobs"
                resolved.active_jobs_path.mkdir(parents=True)
                metadata = {
                    "command_id": correlation.command_id,
                    "batch_id": correlation.batch_id,
                    "enrollment_path": str(correlation.enrollment_path),
                    "manifest_path": str(correlation.manifest_path),
                }
                if defect == "missing_command_id":
                    metadata.pop("command_id")
                elif defect == "mismatched_command_id":
                    metadata["command_id"] = "different-command"
                else:
                    metadata.pop("manifest_path")
                active_job_path = resolved.active_jobs_path / f"{correlation.launch_id}.json"
                active_job_path.write_text(
                    json.dumps(
                        {
                            "launch_id": correlation.launch_id,
                            "job_kind": "rerun_csv",
                            "status": "active",
                            "pid": 24682,
                            "stdout_log": str(root / "untrusted.stdout.log"),
                            "metadata": metadata,
                        }
                    ),
                    encoding="utf-8",
                )
                enrollment = read_rerun_enrollment(correlation.enrollment_path)
                evidence = rerun_correlation_evidence(
                    resolved,
                    enrollment,
                    enrollment_path=correlation.enrollment_path,
                    manifest_path=correlation.manifest_path,
                )

            self.assertFalse(evidence["active_jobs_correlated"])
            self.assertEqual(evidence["active_jobs_correlation_status"], "missing_or_mismatched")
            self.assertEqual(evidence["stdout_log"], "")


if __name__ == "__main__":
    unittest.main()
