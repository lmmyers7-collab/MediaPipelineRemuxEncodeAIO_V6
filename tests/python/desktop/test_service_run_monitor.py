from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from unittest import mock
from datetime import datetime, timezone
from pathlib import Path

from pydantic import ValidationError
from mediapipeline.core.status.run_monitor import (
    RunMonitorStore,
    backend_activity_state_for_run,
    project_run_monitor,
    read_run_monitor_projection,
    seed_starting_run_monitor,
    terminalize_launch_failed_run,
    terminalize_force_stopped_run,
)
from mediapipeline.core.kernel.contracts import QueueAcceptedRunRow
from tests.python.core.contract.test_run_monitor_contract import (
    RUN_ID,
    UPDATED_AT,
    _item,
    _payload,
    _route,
    _worker,
)


NOW = datetime(2026, 7, 16, 15, 0, 20, tzinfo=timezone.utc)


class RunMonitorStoreTests(unittest.TestCase):
    def test_backend_seed_before_spawn_is_exact_idempotent_and_launch_failure_terminalizes(self) -> None:
        accepted = [
            QueueAcceptedRunRow.from_mapping(
                {
                    "source_identity": "source-identity-1",
                    "source_identity_algorithm": "path_size_mtime_sha256.v1",
                    "source_path": r"C:\Media\Django.Unchained.2012.1080p.BluRay.x264.YIFY.mkv",
                    "display_name": "Django Unchained (2012).mkv",
                    "planned_display_name": "Django Unchained (2012).mkv",
                    "planned_display_name_source": "plex_destination_plan.v1",
                    "parent_context": r"C:\Media",
                    "run_queue_index": 1,
                    "run_queue_total": 1,
                    "route": "remux",
                    "route_reason_code": "copy_compatible",
                    "route_reason": "Already compatible",
                    "intended_final_path": r"C:\Final\Movie.mkv",
                }
            )
        ]
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td)
            first = seed_starting_run_monitor(
                state_root,
                run_id="seed-before-spawn",
                command_id="command-1",
                accepted_queue_fingerprint="fingerprint-1",
                accepted_rows=accepted,
                now=NOW,
            )
            (state_root / "RunMonitor" / "latest.json").unlink()
            adopted = seed_starting_run_monitor(
                state_root,
                run_id="seed-before-spawn",
                command_id="command-1",
                accepted_queue_fingerprint="fingerprint-1",
                accepted_rows=accepted,
                now=NOW,
            )

            self.assertEqual(first.write_sequence, 1)
            self.assertEqual(adopted.write_sequence, 1)
            self.assertEqual(RunMonitorStore(state_root).read().run.run_id, "seed-before-spawn")
            self.assertEqual(first.run.lifecycle_state, "starting")
            self.assertEqual(first.items[0].job_id, "seed-before-spawn-item-00000001")
            self.assertEqual(first.items[0].stage("source_discovery").state, "not_started")
            self.assertEqual(first.items[0].routes.planned.route, "remux")
            self.assertEqual(first.items[0].display_name, "Django Unchained (2012).mkv")
            self.assertEqual(
                first.items[0].source_path,
                r"C:\Media\Django.Unchained.2012.1080p.BluRay.x264.YIFY.mkv",
            )

            legacy_payload = dict(accepted[0].raw)
            legacy_payload.pop("planned_display_name", None)
            legacy_payload.pop("planned_display_name_source", None)
            legacy_row = QueueAcceptedRunRow.from_mapping(legacy_payload)
            with self.assertRaisesRegex(ValueError, "verified planned display-name evidence"):
                seed_starting_run_monitor(
                    state_root,
                    run_id="legacy-unverified-name",
                    command_id="command-legacy-name",
                    accepted_queue_fingerprint="fingerprint-legacy-name",
                    accepted_rows=[legacy_row],
                    now=NOW,
                )

            with self.assertRaisesRegex(ValueError, "verified planned display-name evidence"):
                seed_starting_run_monitor(
                    state_root,
                    run_id="blank-display-name",
                    command_id="command-blank-name",
                    accepted_queue_fingerprint="fingerprint-blank-name",
                    accepted_rows=[replace(accepted[0], planned_display_name="")],
                    now=NOW,
                )

            changed = [QueueAcceptedRunRow.from_mapping({**accepted[0].raw, "route": "encode"})]
            with self.assertRaisesRegex(ValueError, "exact starting monitor"):
                seed_starting_run_monitor(
                    state_root,
                    run_id="seed-before-spawn",
                    command_id="command-1",
                    accepted_queue_fingerprint="fingerprint-1",
                    accepted_rows=changed,
                    now=NOW,
                )

            terminalized = terminalize_launch_failed_run(
                state_root,
                "seed-before-spawn",
                reason="synthetic spawn failure",
                now=NOW,
            )
            failed = RunMonitorStore(state_root).read("seed-before-spawn")

        self.assertTrue(terminalized)
        self.assertIsNotNone(failed)
        assert failed is not None
        self.assertEqual(failed.run.lifecycle_state, "failed")
        self.assertEqual(failed.run.outcome.reason_code, "PIPELINE_LAUNCH_FAILED")
        self.assertEqual([item.lifecycle_state for item in failed.items], ["failed"])
        self.assertEqual(failed.items[0].stage("final_evidence").state, "failed")
        self.assertEqual(failed.items[0].routes.final.state, "unknown")
        self.assertEqual(failed.items[0].routes.final.reason_code, "PIPELINE_LAUNCH_FAILED")
        self.assertEqual(failed.items[0].routes.final.reason, "synthetic spawn failure")
        self.assertEqual(failed.items[0].routes.final.evidence.source, "pipeline_launch")

    def test_atomic_store_preserves_latest_valid_run_and_survives_restart(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td)
            store = RunMonitorStore(state_root, retention_count=10)
            first = _payload([_item(1, 1)])
            store.write(first)

            invalid = _payload([_item(1, 2)])
            with self.assertRaises(ValidationError):
                store.write(invalid)

            restarted = RunMonitorStore(state_root, retention_count=10)
            record = restarted.read()
            pointer = json.loads((state_root / "RunMonitor" / "latest.json").read_text(encoding="utf-8"))

            self.assertIsNotNone(record)
            self.assertEqual(record.run.run_id, RUN_ID)
            self.assertEqual(len(record.items), 1)
            self.assertEqual(pointer["schema_version"], "pipeline_run_monitor_pointer.v1")
            self.assertEqual(pointer["run_id"], RUN_ID)
            self.assertEqual(list((state_root / "RunMonitor").glob("*.tmp")), [])

    def test_store_rejects_stale_sequence_membership_change_and_terminal_regression(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td)
            store = RunMonitorStore(state_root)
            initial = _payload([_item(1, 1, lifecycle_state="completed")], lifecycle_state="completed")
            initial["write_sequence"] = 5
            store.write(initial)

            stale = json.loads(json.dumps(initial))
            stale["write_sequence"] = 5
            with self.assertRaisesRegex(ValueError, "write_sequence"):
                store.write(stale)

            membership_change = json.loads(json.dumps(initial))
            membership_change["write_sequence"] = 6
            membership_change["items"][0]["source_identity"]["value"] = "different-source"
            with self.assertRaisesRegex(ValueError, "membership"):
                store.write(membership_change)

            for label, mutate in (
                ("fingerprint", lambda payload: payload["run"]["accepted_queue"].__setitem__("fingerprint", "different-plan")),
                ("display name", lambda payload: payload["items"][0].__setitem__("display_name", "Different.mkv")),
                ("planned reason", lambda payload: payload["items"][0]["routes"]["planned"].__setitem__("reason", "Different policy")),
            ):
                with self.subTest(immutable=label):
                    changed_evidence = json.loads(json.dumps(initial))
                    changed_evidence["write_sequence"] = 6
                    mutate(changed_evidence)
                    with self.assertRaisesRegex(ValueError, "membership"):
                        store.write(changed_evidence)

            regression = _payload([_item(1, 1)], lifecycle_state="running")
            regression["write_sequence"] = 6
            with self.assertRaisesRegex(ValueError, "terminal"):
                store.write(regression)

            terminal_rewrite = _payload(
                [_item(1, 1, lifecycle_state="failed")],
                lifecycle_state="failed",
            )
            terminal_rewrite["write_sequence"] = 6
            with self.assertRaisesRegex(ValueError, "terminal"):
                store.write(terminal_rewrite)

    def test_retention_never_removes_active_runs_and_keeps_bounded_terminal_history(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td)
            store = RunMonitorStore(state_root, retention_count=2)
            for index in range(1, 5):
                payload = _payload([_item(1, 1, lifecycle_state="completed")], lifecycle_state="completed")
                payload["run"]["run_id"] = f"terminal-{index}"
                payload["items"][0]["job_id"] = f"terminal-{index}:item:1"
                store.write(payload)
            active = _payload([_item(1, 1)], lifecycle_state="running")
            active["run"]["run_id"] = "active-run"
            active["items"][0]["job_id"] = "active-run:item:1"
            active["current_workers"] = [_worker(1, "active-run:item:1")]
            active["current_workers"][0]["run_id"] = "active-run"
            store.write(active)

            names = {path.stem for path in (state_root / "RunMonitor").glob("*.json") if path.name != "latest.json"}

            self.assertIn("active-run", names)
            self.assertEqual({name for name in names if name.startswith("terminal-")}, {"terminal-3", "terminal-4"})

    def test_run_id_paths_reject_traversal_separators_drives_unc_and_reserved_pointer_name(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            store = RunMonitorStore(Path(td))
            for unsafe in ("../escape", r"folder\escape", "folder/escape", r"C:\escape", r"\\server\share", "latest", ""):
                with self.subTest(run_id=unsafe):
                    with self.assertRaisesRegex(ValueError, "unsafe"):
                        store.path_for_run(unsafe)

    def test_pointer_identity_never_trusts_a_declared_path_or_mismatched_target(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td)
            monitor_root = state_root / "RunMonitor"
            monitor_root.mkdir()
            (monitor_root / "latest.json").write_text(
                json.dumps(
                    {
                        "schema_version": "pipeline_run_monitor_pointer.v1",
                        "run_id": "safe-run",
                        "updated_at": "2026-07-16T15:00:00Z",
                        "path": r"C:\outside\monitor.json",
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaises(ValidationError):
                RunMonitorStore(state_root).read()

            (monitor_root / "latest.json").write_text(
                json.dumps(
                    {
                        "schema_version": "pipeline_run_monitor_pointer.v1",
                        "run_id": "safe-run",
                        "updated_at": "2026-07-16T15:00:00Z",
                    }
                ),
                encoding="utf-8",
            )
            mismatched = _payload([_item(1, 1)])
            (monitor_root / "safe-run.json").write_text(json.dumps(mismatched), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "filename and run_id"):
                RunMonitorStore(state_root).read()

    def test_atomic_replace_retries_transient_windows_permission_error_and_cleans_temp(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td)
            store = RunMonitorStore(state_root)
            from mediapipeline.core.status import run_monitor_storage

            original_replace = run_monitor_storage.os.replace
            attempts = 0

            def flaky_replace(source: Path, destination: Path) -> None:
                nonlocal attempts
                attempts += 1
                if attempts == 1:
                    raise PermissionError("temporary scanner lock")
                original_replace(source, destination)

            with mock.patch.object(run_monitor_storage.os, "replace", side_effect=flaky_replace):
                store.write(_payload([_item(1, 1)]))

            self.assertGreaterEqual(attempts, 3)  # run file retries once, then pointer replaces once
            self.assertEqual(list((state_root / "RunMonitor").glob("*.tmp")), [])


class RunMonitorProjectionTests(unittest.TestCase):
    def test_force_stop_closes_unproven_final_route_and_preserves_existing_terminal_route(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td)
            unproven = _item(1, 2, lifecycle_state="active", active_stage="transcode")
            unproven["audio"]["tracks"] = [
                {
                    "track_id": "audio:1",
                    "stream_index": 1,
                    "state": "awaiting_evidence",
                    "evidence": unproven["audio"]["evidence"],
                }
            ]
            unproven["subtitles"]["tracks"] = [
                {
                    "track_id": "subtitle:2",
                    "stream_index": 2,
                    "state": "awaiting_evidence",
                    "evidence": unproven["subtitles"]["evidence"],
                }
            ]
            proven = _item(2, 2, lifecycle_state="active", active_stage="publish")
            proven["routes"]["final"] = _route(
                "available",
                route="remux",
                reason="Terminal route already proven",
                source="completed_sidecar",
            )
            store = RunMonitorStore(state_root)
            store.write(
                _payload(
                    [unproven, proven],
                    workers=[
                        _worker(1, str(unproven["job_id"]), stage_id="transcode"),
                        _worker(2, str(proven["job_id"]), stage_id="publish"),
                    ],
                )
            )

            changed = terminalize_force_stopped_run(state_root, RUN_ID, now=NOW)
            record = store.read(RUN_ID)

        self.assertTrue(changed)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.items[0].routes.final.state, "unknown")
        self.assertEqual(record.items[0].routes.final.reason_code, "force_stopped_by_operator")
        self.assertEqual(record.items[0].routes.final.evidence.source, "force_stop_control")
        self.assertEqual(record.items[0].audio.tracks[0].state, "unknown")
        self.assertEqual(record.items[0].audio.tracks[0].completed_at, "")
        self.assertEqual(record.items[0].subtitles.tracks[0].state, "unknown")
        self.assertEqual(record.items[0].subtitles.tracks[0].completed_at, "")
        self.assertEqual(record.items[1].routes.final.state, "available")
        self.assertEqual(record.items[1].routes.final.route, "remux")
        self.assertEqual(record.items[1].routes.final.evidence.source, "completed_sidecar")

    def test_force_stop_preserves_previously_verified_output_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td)
            item = _item(1, 1, lifecycle_state="active", active_stage="publish")
            item["output"].update(
                {
                    "state": "verified",
                    "scratch_path": r"C:\Scratch\Movie.mkv",
                    "working_output_path": r"C:\Scratch\Movie.verified.mkv",
                    "size_bytes": 12345,
                    "verification_state": "completed",
                    "evidence": {
                        "source": "output_evidence",
                        "provenance": "backend_confirmed",
                        "recorded_at": "2026-07-16T15:00:00Z",
                    },
                }
            )
            store = RunMonitorStore(state_root)
            store.write(_payload([item], workers=[_worker(1, str(item["job_id"]), stage_id="publish")]))

            changed = terminalize_force_stopped_run(state_root, RUN_ID, now=NOW)
            record = store.read(RUN_ID)

        self.assertTrue(changed)
        self.assertIsNotNone(record)
        assert record is not None
        self.assertEqual(record.items[0].output.state, "verified")
        self.assertEqual(record.items[0].output.verification_state, "completed")
        self.assertEqual(record.items[0].output.working_output_path, r"C:\Scratch\Movie.verified.mkv")
        self.assertEqual(record.items[0].output.evidence.source, "output_evidence")

    def test_unknown_backend_activity_suppresses_fresh_nonterminal_claims(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="transcode")
        item["routes"]["executed"] = _route(
            "available",
            route="encode_hardware",
            reason="Runtime route",
            source="route_selected_event",
        )
        payload = _payload([item], workers=[_worker(1, str(item["job_id"]))])

        projection = project_run_monitor(payload, now=NOW, backend_activity_state="unknown")

        self.assertEqual(projection["freshness"]["state"], "unknown")
        self.assertEqual(projection["freshness"]["reason_code"], "backend_activity_unknown")
        self.assertEqual(projection["current_workers"], [])
        self.assertEqual(projection["items"][0]["lifecycle_state"], "unknown")
        self.assertIsNone(projection["items"][0]["current_stage"])
        self.assertEqual(projection["items"][0]["executed_route"]["state"], "unknown")
        self.assertEqual(projection["items"][0]["executed_route"]["value"], "")
        self.assertEqual(projection["last_known"]["label"], "Last known — not current")

    def test_backend_activity_requires_exact_run_metadata_and_reports_all_terminal_states_idle(self) -> None:
        rows = [
            {
                "source": "contract",
                "job_kind": "pipeline",
                "mode": "once",
                "status": "active",
                "metadata": {"run_id": "different-run"},
            },
            {
                "source": "contract",
                "job_kind": "pipeline",
                "mode": "once",
                "status": "completed",
                "metadata": {"run_id": RUN_ID},
            },
        ]
        with mock.patch(
            "mediapipeline.core.status.run_monitor.active_job_detail_rows",
            return_value=rows,
        ):
            self.assertEqual(backend_activity_state_for_run(Path("unused"), RUN_ID), "confirmed_idle")

        rows[1]["status"] = "active"
        with mock.patch(
            "mediapipeline.core.status.run_monitor.active_job_detail_rows",
            return_value=rows,
        ):
            self.assertEqual(backend_activity_state_for_run(Path("unused"), RUN_ID), "confirmed_active")

        rows[1]["metadata"] = {"run_id": f"{RUN_ID}-similar"}
        with mock.patch(
            "mediapipeline.core.status.run_monitor.active_job_detail_rows",
            return_value=rows,
        ):
            self.assertEqual(backend_activity_state_for_run(Path("unused"), RUN_ID), "unknown")

    def test_current_projection_exposes_every_active_worker_and_separate_route_authorities(self) -> None:
        items = [
            _item(1, 2, lifecycle_state="active", active_stage="transcode"),
            _item(2, 2, lifecycle_state="active", active_stage="verification"),
        ]
        items[0]["routes"]["executed"] = _route(
            "available", route="encode_hardware", reason="Hardware route selected", source="route_selected_event"
        )
        items[1]["routes"]["executed"] = _route(
            "available", route="remux", reason="Streams are compatible", source="route_selected_event"
        )
        workers = [_worker(1, str(items[0]["job_id"])), _worker(2, str(items[1]["job_id"]), stage_id="verification")]

        projection = project_run_monitor(_payload(items, workers=workers), now=NOW, backend_activity_state="confirmed_active")

        self.assertEqual(projection["schema_version"], "desktop_run_monitor.v1")
        self.assertEqual(projection["freshness"]["state"], "current")
        self.assertEqual(len(projection["current_workers"]), 2)
        self.assertEqual(projection["items"][0]["planned_route"]["label"], "Planned route")
        self.assertEqual(projection["items"][0]["executed_route"]["label"], "Executed route")
        self.assertEqual(projection["items"][0]["final_route"]["state"], "awaiting_evidence")
        self.assertEqual(projection["items"][0]["current_stage"]["stage_id"], "transcode")
        self.assertEqual(projection["items"][1]["current_stage"]["stage_id"], "verification")

    def test_explicit_worker_route_contradiction_suppresses_current_but_aliases_and_awaiting_are_allowed(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="transcode")
        item["routes"]["executed"] = _route(
            "available",
            route="encode_hardware",
            reason="Hardware encoder selected",
            source="route_selected_event",
        )
        worker = _worker(1, str(item["job_id"]))
        worker["route"] = "encode-cpu-fallback"

        contradictory = project_run_monitor(
            _payload([item], workers=[worker]),
            now=NOW,
            backend_activity_state="confirmed_active",
        )
        self.assertEqual(contradictory["freshness"]["state"], "unknown")
        self.assertEqual(contradictory["freshness"]["reason_code"], "contradictory_worker_route")
        self.assertEqual(contradictory["current_workers"], [])

        item["routes"]["executed"] = _route(
            "available",
            route="encode-cpu-fallback",
            reason="CPU fallback selected",
            source="route_selected_event",
        )
        worker["route"] = "cpu_encode_fallback"
        alias_match = project_run_monitor(
            _payload([item], workers=[worker]),
            now=NOW,
            backend_activity_state="confirmed_active",
        )
        self.assertEqual(alias_match["freshness"]["state"], "current")

        item["routes"]["executed"] = _route("awaiting_evidence")
        awaiting = project_run_monitor(
            _payload([item], workers=[worker]),
            now=NOW,
            backend_activity_state="confirmed_active",
        )
        self.assertEqual(awaiting["freshness"]["state"], "current")

    def test_active_item_without_one_backend_stage_is_contradictory(self) -> None:
        item = _item(1, 1, lifecycle_state="active")

        projection = project_run_monitor(
            _payload([item]),
            now=NOW,
            backend_activity_state="confirmed_active",
        )

        self.assertEqual(projection["freshness"]["state"], "unknown")
        self.assertEqual(projection["freshness"]["reason_code"], "contradictory_item_stage")
        self.assertIsNone(projection["items"][0]["current_stage"])

    def test_starting_worker_without_stage_heartbeat_is_current_but_does_not_claim_an_active_stage(self) -> None:
        item = _item(1, 1, lifecycle_state="active")
        worker = _worker(1, str(item["job_id"]), stage_id="accepted")
        worker.update(
            state="starting",
            route="",
            progress={"kind": "none"},
            evidence={
                "source": "worker_claim",
                "provenance": "backend_confirmed",
                "recorded_at": UPDATED_AT,
            },
        )

        projection = project_run_monitor(
            _payload([item], workers=[worker]),
            now=NOW,
            backend_activity_state="confirmed_active",
        )

        self.assertEqual(projection["freshness"]["state"], "current")
        self.assertEqual(projection["current_workers"][0]["state"], "starting")
        self.assertEqual(projection["current_workers"][0]["stage_id"], "accepted")
        self.assertEqual(projection["current_workers"][0]["route"], "")
        self.assertIsNone(projection["items"][0]["current_stage"])

    def test_route_projection_preserves_awaiting_not_applicable_and_unknown_states(self) -> None:
        item = _item(1, 1)
        item["routes"]["executed"] = _route("not_applicable")
        item["routes"]["final"] = _route("unknown")
        item["routes"]["final"].update(
            reason="Source probe failed before route selection.",
            reason_code="SOURCE_PROBE_FAILED",
            evidence={
                "source": "failure_artifact",
                "provenance": "terminal",
                "recorded_at": UPDATED_AT,
            },
        )

        projection = project_run_monitor(_payload([item]), now=NOW, backend_activity_state="confirmed_active")

        self.assertEqual(projection["items"][0]["executed_route"]["state"], "not_applicable")
        self.assertEqual(projection["items"][0]["final_route"]["state"], "unknown")
        self.assertEqual(projection["items"][0]["final_route"]["reason"], "Source probe failed before route selection.")
        self.assertEqual(projection["items"][0]["final_route"]["reason_code"], "SOURCE_PROBE_FAILED")
        self.assertEqual(projection["items"][0]["final_route"]["evidence"]["source"], "failure_artifact")
        self.assertEqual(projection["items"][0]["executed_route"]["label"], "Executed route")
        self.assertEqual(projection["items"][0]["final_route"]["label"], "Final route")

    def test_stale_evidence_cannot_populate_current_file_stage_route_worker_or_percent(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="transcode")
        item["routes"]["executed"] = _route("available", route="encode", reason="Runtime route", source="route_selected_event")
        payload = _payload([item], workers=[_worker(1, str(item["job_id"]))])
        payload["run"]["updated_at"] = "2026-07-16T14:58:00Z"

        projection = project_run_monitor(payload, now=NOW, backend_activity_state="confirmed_active", stale_after_seconds=45)

        self.assertEqual(projection["freshness"]["state"], "stale")
        self.assertEqual(projection["current_workers"], [])
        self.assertEqual(projection["items"][0]["lifecycle_state"], "unknown")
        self.assertIsNone(projection["items"][0]["current_stage"])
        self.assertEqual(projection["items"][0]["executed_route"]["state"], "unknown")
        self.assertEqual(projection["items"][0]["executed_route"]["value"], "")
        self.assertIsNone(projection["items"][0]["current_progress"])
        self.assertEqual(projection["last_known"]["items"][0]["current_stage"]["stage_id"], "transcode")
        self.assertEqual(projection["last_known"]["items"][0]["executed_route"]["value"], "encode")
        self.assertGreater(projection["freshness"]["age_seconds"], 45)

    def test_stale_active_liveness_preserves_already_terminal_file_proof(self) -> None:
        completed = _item(1, 2, lifecycle_state="completed")
        completed["routes"]["executed"] = _route(
            "available",
            route="encode_hardware",
            reason="Runtime hardware route",
            source="route_selected_event",
        )
        completed["routes"]["final"] = _route(
            "available",
            route="encode_hardware",
            reason="Verified direct publication",
            source="completed_sidecar",
        )
        completed["output"].update(
            state="published",
            published_path=r"C:\Final\Movie-0001.mkv",
            intended_final_path=r"C:\Final\Movie-0001.mkv",
            verification_state="completed",
            evidence=_route("available", route="encode_hardware", source="completed_sidecar")["evidence"],
        )
        completed["terminal_references"] = [
            {
                "kind": "completed",
                "reference": "completed:source-v2-1",
                "path": r"C:\State\Completed\source-v2-1.json",
                "evidence": _route("available", route="encode_hardware", source="completed_sidecar")["evidence"],
            }
        ]
        active = _item(2, 2, lifecycle_state="active", active_stage="transcode")
        worker = _worker(1, str(active["job_id"]))
        worker["updated_at"] = "2026-07-16T14:58:00Z"
        worker["evidence"]["recorded_at"] = "2026-07-16T14:58:00Z"
        payload = _payload([completed, active], workers=[worker])
        payload["run"]["updated_at"] = "2026-07-16T15:00:19Z"

        projection = project_run_monitor(
            payload,
            now=NOW,
            backend_activity_state="confirmed_active",
            stale_after_seconds=45,
        )

        self.assertEqual(projection["freshness"]["state"], "stale")
        self.assertEqual(projection["current_workers"], [])
        self.assertEqual(projection["items"][0]["lifecycle_state"], "completed")
        self.assertEqual(projection["items"][0]["final_route"]["value"], "encode_hardware")
        self.assertEqual(projection["items"][0]["output"]["published_path"], r"C:\Final\Movie-0001.mkv")
        self.assertEqual(projection["items"][0]["terminal_references"][0]["kind"], "completed")
        self.assertEqual(projection["items"][1]["lifecycle_state"], "unknown")
        self.assertIsNone(projection["items"][1]["current_stage"])

    def test_fresh_envelope_write_cannot_mask_a_stale_active_worker(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="transcode")
        item["routes"]["executed"] = _route(
            "available",
            route="encode_hardware",
            reason="Runtime route",
            source="route_selected_event",
        )
        worker = _worker(1, str(item["job_id"]))
        worker["updated_at"] = "2026-07-16T14:58:00Z"
        worker["evidence"]["recorded_at"] = "2026-07-16T14:58:00Z"
        payload = _payload([item], workers=[worker])
        payload["run"]["updated_at"] = "2026-07-16T15:00:19Z"
        payload["run"]["evidence"]["recorded_at"] = "2026-07-16T15:00:19Z"

        projection = project_run_monitor(
            payload,
            now=NOW,
            backend_activity_state="confirmed_active",
            stale_after_seconds=45,
        )

        self.assertEqual(projection["freshness"]["state"], "stale")
        self.assertEqual(projection["freshness"]["reason_code"], "current_evidence_stale")
        self.assertEqual(projection["freshness"]["updated_at"], "2026-07-16T14:58:00Z")
        self.assertEqual(projection["current_workers"], [])
        self.assertEqual(projection["items"][0]["lifecycle_state"], "unknown")
        self.assertIsNone(projection["items"][0]["current_stage"])
        self.assertEqual(projection["items"][0]["executed_route"]["state"], "unknown")
        self.assertEqual(projection["last_known"]["updated_at"], "2026-07-16T14:58:00Z")

    def test_future_timestamp_is_unknown_and_suppresses_current_claims(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="copy_to_scratch")
        payload = _payload([item], workers=[_worker(1, str(item["job_id"]), stage_id="copy_to_scratch")])
        payload["run"]["updated_at"] = "2026-07-16T15:02:00Z"

        projection = project_run_monitor(payload, now=NOW, backend_activity_state="confirmed_active", future_tolerance_seconds=5)

        self.assertEqual(projection["freshness"]["state"], "unknown")
        self.assertEqual(projection["freshness"]["reason_code"], "future_timestamp")
        self.assertEqual(projection["current_workers"], [])
        self.assertIsNone(projection["items"][0]["current_stage"])

    def test_any_future_dated_worker_claim_suppresses_the_shared_current_projection(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="copy_to_scratch")
        worker = _worker(1, str(item["job_id"]), stage_id="copy_to_scratch")
        worker["evidence"]["recorded_at"] = "2026-07-16T15:02:00Z"
        payload = _payload([item], workers=[worker])

        projection = project_run_monitor(
            payload,
            now=NOW,
            backend_activity_state="confirmed_active",
            future_tolerance_seconds=5,
        )

        self.assertEqual(projection["freshness"]["state"], "unknown")
        self.assertEqual(projection["freshness"]["reason_code"], "current_evidence_future_timestamp")
        self.assertEqual(projection["current_workers"], [])
        self.assertIsNone(projection["items"][0]["current_stage"])

    def test_future_dated_active_stage_is_not_masked_by_a_current_worker(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="transcode")
        active_stage = next(stage for stage in item["stages"] if stage["stage_id"] == "transcode")
        active_stage["updated_at"] = "2026-07-16T15:02:00Z"
        active_stage["evidence"]["recorded_at"] = "2026-07-16T15:02:00Z"
        payload = _payload([item], workers=[_worker(1, str(item["job_id"]))])

        projection = project_run_monitor(
            payload,
            now=NOW,
            backend_activity_state="confirmed_active",
            future_tolerance_seconds=5,
        )

        self.assertEqual(projection["freshness"]["state"], "unknown")
        self.assertEqual(projection["freshness"]["reason_code"], "current_evidence_future_timestamp")
        self.assertEqual(projection["current_workers"], [])
        self.assertIsNone(projection["items"][0]["current_stage"])

    def test_future_dated_active_audio_or_subtitle_track_is_not_masked_by_a_current_worker(self) -> None:
        for collection_name, stage_id, track in (
            (
                "audio",
                "transcode",
                {
                    "track_id": "audio:1",
                    "stream_index": 1,
                    "state": "active",
                    "started_at": UPDATED_AT,
                    "updated_at": "2026-07-16T15:02:00Z",
                    "evidence": {
                        "source": "ffmpeg_progress",
                        "provenance": "engine_event",
                        "recorded_at": "2026-07-16T15:02:00Z",
                    },
                },
            ),
            (
                "subtitles",
                "subtitles",
                {
                    "track_id": "subtitle:2",
                    "stream_index": 2,
                    "state": "active",
                    "started_at": UPDATED_AT,
                    "updated_at": "2026-07-16T15:02:00Z",
                    "evidence": {
                        "source": "subtitle_ocr",
                        "provenance": "engine_event",
                        "recorded_at": "2026-07-16T15:02:00Z",
                    },
                },
            ),
        ):
            with self.subTest(collection=collection_name):
                item = _item(1, 1, lifecycle_state="active", active_stage=stage_id)
                item[collection_name] = {
                    "state": "active",
                    "policy_final": True,
                    "tracks": [track],
                    "evidence": {
                        "source": f"{collection_name}_policy",
                        "provenance": "backend_confirmed",
                        "recorded_at": UPDATED_AT,
                    },
                }
                payload = _payload([item], workers=[_worker(1, str(item["job_id"]), stage_id=stage_id)])

                projection = project_run_monitor(
                    payload,
                    now=NOW,
                    backend_activity_state="confirmed_active",
                    future_tolerance_seconds=5,
                )

                self.assertEqual(projection["freshness"]["state"], "unknown")
                self.assertEqual(projection["freshness"]["reason_code"], "current_evidence_future_timestamp")
                self.assertEqual(projection["current_workers"], [])
                self.assertEqual(projection["items"][0][collection_name]["state"], "unknown")

    def test_future_dated_active_track_evidence_is_not_masked_by_a_current_track_timestamp(self) -> None:
        for collection_name, stage_id, track in (
            (
                "audio",
                "transcode",
                {"track_id": "audio:1", "stream_index": 1},
            ),
            (
                "subtitles",
                "subtitles",
                {"track_id": "subtitle:2", "stream_index": 2},
            ),
        ):
            with self.subTest(collection=collection_name):
                item = _item(1, 1, lifecycle_state="active", active_stage=stage_id)
                item[collection_name] = {
                    "state": "active",
                    "policy_final": True,
                    "tracks": [
                        {
                            **track,
                            "state": "active",
                            "started_at": UPDATED_AT,
                            "updated_at": UPDATED_AT,
                            "evidence": {
                                "source": f"{collection_name}_runtime",
                                "provenance": "engine_event",
                                "recorded_at": "2026-07-16T15:02:00Z",
                            },
                        }
                    ],
                    "evidence": {
                        "source": f"{collection_name}_runtime",
                        "provenance": "backend_confirmed",
                        "recorded_at": UPDATED_AT,
                    },
                }
                payload = _payload([item], workers=[_worker(1, str(item["job_id"]), stage_id=stage_id)])

                projection = project_run_monitor(
                    payload,
                    now=NOW,
                    backend_activity_state="confirmed_active",
                    future_tolerance_seconds=5,
                )

                self.assertEqual(projection["freshness"]["state"], "unknown")
                self.assertEqual(projection["freshness"]["reason_code"], "current_evidence_future_timestamp")
                self.assertEqual(projection["current_workers"], [])
                self.assertEqual(projection["items"][0][collection_name]["state"], "unknown")

    def test_blank_active_audio_or_subtitle_track_update_is_rejected_before_freshness(self) -> None:
        for collection_name, stage_id, track in (
            ("audio", "transcode", {"track_id": "audio:1", "stream_index": 1}),
            ("subtitles", "subtitles", {"track_id": "subtitle:2", "stream_index": 2}),
        ):
            with self.subTest(collection=collection_name):
                item = _item(1, 1, lifecycle_state="active", active_stage=stage_id)
                item[collection_name] = {
                    "state": "active",
                    "tracks": [
                        {
                            **track,
                            "state": "active",
                            "started_at": UPDATED_AT,
                            "updated_at": "",
                            "evidence": {
                                "source": f"{collection_name}_runtime",
                                "provenance": "engine_event",
                                "recorded_at": "2026-07-16T15:02:00Z",
                            },
                        }
                    ],
                    "evidence": {
                        "source": f"{collection_name}_runtime",
                        "provenance": "backend_confirmed",
                        "recorded_at": UPDATED_AT,
                    },
                }

                label = "subtitle" if collection_name == "subtitles" else collection_name
                with self.assertRaisesRegex(ValidationError, f"active {label} track"):
                    project_run_monitor(
                        _payload([item]),
                        now=NOW,
                        backend_activity_state="confirmed_active",
                    )

    def test_stale_active_track_is_not_masked_by_a_fresh_worker(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="subtitles")
        item["subtitles"] = {
            "state": "active",
            "policy_final": True,
            "tracks": [
                {
                    "track_id": "subtitle:2",
                    "stream_index": 2,
                    "state": "active",
                    "started_at": "2026-07-16T14:58:00Z",
                    "updated_at": "2026-07-16T14:58:00Z",
                    "evidence": {
                        "source": "subtitle_ocr",
                        "provenance": "engine_event",
                        "recorded_at": "2026-07-16T14:58:00Z",
                    },
                }
            ],
            "evidence": {
                "source": "subtitle_policy",
                "provenance": "backend_confirmed",
                "recorded_at": UPDATED_AT,
            },
        }
        payload = _payload([item], workers=[_worker(1, str(item["job_id"]), stage_id="subtitles")])

        projection = project_run_monitor(
            payload,
            now=NOW,
            backend_activity_state="confirmed_active",
            stale_after_seconds=45,
        )

        self.assertEqual(projection["freshness"]["state"], "stale")
        self.assertEqual(projection["freshness"]["reason_code"], "current_evidence_stale")
        self.assertEqual(projection["current_workers"], [])
        self.assertEqual(projection["items"][0]["subtitles"]["state"], "unknown")

    def test_current_projection_preserves_backend_subtitle_step_unit_and_cue_evidence(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="subtitles")
        item["subtitles"] = {
            "state": "active",
            "policy_final": True,
            "tracks": [
                {
                    "track_id": "subtitle:2",
                    "stream_index": 2,
                    "language": "eng",
                    "state": "active",
                    "started_at": UPDATED_AT,
                    "updated_at": UPDATED_AT,
                    "step_index": 2,
                    "step_total": 4,
                    "step_name": "convert_ocr",
                    "progress_unit": "pages",
                    "cue_count": 17,
                    "progress": {"kind": "determinate", "numerator": 3, "denominator": 10},
                    "evidence": {
                        "source": "subtitle_ocr",
                        "provenance": "engine_event",
                        "recorded_at": UPDATED_AT,
                    },
                }
            ],
            "evidence": {
                "source": "subtitle_policy",
                "provenance": "backend_confirmed",
                "recorded_at": UPDATED_AT,
            },
        }
        payload = _payload([item], workers=[_worker(1, str(item["job_id"]), stage_id="subtitles")])

        projection = project_run_monitor(payload, now=NOW, backend_activity_state="confirmed_active")

        track = projection["items"][0]["subtitles"]["tracks"][0]
        self.assertEqual(track["step_index"], 2)
        self.assertEqual(track["step_total"], 4)
        self.assertEqual(track["step_name"], "convert_ocr")
        self.assertEqual(track["progress_unit"], "pages")
        self.assertEqual(track["cue_count"], 17)
        self.assertEqual(track["progress"], {"kind": "determinate", "numerator": 3.0, "denominator": 10.0})

    def test_future_dated_terminal_record_is_not_trusted_only_because_it_is_terminal(self) -> None:
        item = _item(1, 1, lifecycle_state="completed")
        item["routes"]["final"] = _route(
            "available",
            route="encode_cpu_fallback",
            reason="Terminal sidecar route",
            source="completed_sidecar",
        )
        payload = _payload([item], lifecycle_state="completed")
        payload["run"]["updated_at"] = "2026-07-16T15:02:00Z"
        payload["run"]["evidence"]["recorded_at"] = "2026-07-16T15:02:00Z"

        projection = project_run_monitor(
            payload,
            now=NOW,
            backend_activity_state="confirmed_idle",
            future_tolerance_seconds=5,
        )

        self.assertEqual(projection["freshness"]["state"], "unknown")
        self.assertEqual(projection["freshness"]["reason_code"], "future_timestamp")
        self.assertEqual(projection["run"]["lifecycle_state"], "unknown")
        self.assertEqual(projection["items"][0]["lifecycle_state"], "unknown")
        self.assertEqual(projection["items"][0]["final_route"]["state"], "unknown")
        self.assertEqual(projection["last_known"]["items"][0]["lifecycle_state"], "completed")
        self.assertEqual(projection["last_known"]["items"][0]["final_route"]["value"], "encode_cpu_fallback")

    def test_future_dated_final_route_evidence_suppresses_terminal_proof(self) -> None:
        item = _item(1, 1, lifecycle_state="completed")
        item["routes"]["final"] = _route(
            "available",
            route="remux",
            reason="Verified terminal route",
            source="completed_sidecar",
        )
        item["routes"]["final"]["evidence"]["recorded_at"] = "2026-07-16T15:02:00Z"

        projection = project_run_monitor(
            _payload([item], lifecycle_state="completed"),
            now=NOW,
            backend_activity_state="confirmed_idle",
            future_tolerance_seconds=5,
        )

        self.assertEqual(projection["freshness"]["state"], "unknown")
        self.assertEqual(projection["freshness"]["reason_code"], "future_timestamp")
        self.assertEqual(projection["items"][0]["lifecycle_state"], "unknown")
        self.assertEqual(projection["items"][0]["final_route"]["state"], "unknown")
        self.assertEqual(projection["items"][0]["final_route"]["value"], "")
        self.assertEqual(projection["last_known"]["items"][0]["final_route"]["value"], "remux")

    def test_future_dated_terminal_output_or_artifact_evidence_suppresses_terminal_proof(self) -> None:
        for claim in ("output", "terminal_reference"):
            with self.subTest(claim=claim):
                item = _item(1, 1, lifecycle_state="completed")
                item["output"].update(
                    {
                        "state": "published",
                        "published_path": r"D:\Library\Movie.mkv",
                        "intended_final_path": r"D:\Library\Movie.mkv",
                        "verification_state": "completed",
                        "evidence": {
                            "source": "completed_output",
                            "provenance": "terminal",
                            "recorded_at": UPDATED_AT,
                        },
                    }
                )
                item["terminal_references"] = [
                    {
                        "kind": "completed",
                        "reference": "completed:movie-1",
                        "path": r"D:\Library\Movie.mkv",
                        "evidence": {
                            "source": "completed_artifact",
                            "provenance": "terminal",
                            "recorded_at": UPDATED_AT,
                        },
                    }
                ]
                if claim == "output":
                    item["output"]["evidence"]["recorded_at"] = "2026-07-16T15:02:00Z"
                else:
                    item["terminal_references"][0]["evidence"]["recorded_at"] = "2026-07-16T15:02:00Z"

                projection = project_run_monitor(
                    _payload([item], lifecycle_state="completed"),
                    now=NOW,
                    backend_activity_state="confirmed_idle",
                    future_tolerance_seconds=5,
                )

                self.assertEqual(projection["freshness"]["state"], "unknown")
                self.assertEqual(projection["freshness"]["reason_code"], "future_timestamp")
                self.assertEqual(projection["items"][0]["output"]["state"], "unknown")
                self.assertEqual(projection["items"][0]["output"]["published_path"], "")
                self.assertEqual(projection["items"][0]["terminal_references"], [])
                self.assertEqual(projection["items"][0]["display_name"], "Movie-0001.mkv")
                self.assertEqual(projection["items"][0]["display_name_basis"], "legacy_accepted")
                self.assertEqual(projection["last_known"]["items"][0]["output"]["state"], "published")
                self.assertEqual(projection["last_known"]["items"][0]["display_name"], "Movie-0001.mkv")
                self.assertEqual(projection["last_known"]["items"][0]["display_name_basis"], "legacy_accepted")

    def test_backend_confirmed_idle_contradiction_suppresses_raw_active_history(self) -> None:
        item = _item(1, 1, lifecycle_state="active", active_stage="verification")
        payload = _payload([item], workers=[_worker(1, str(item["job_id"]), stage_id="verification")])

        projection = project_run_monitor(payload, now=NOW, backend_activity_state="confirmed_idle")

        self.assertEqual(projection["freshness"]["state"], "unknown")
        self.assertEqual(projection["freshness"]["reason_code"], "contradictory_backend_idle")
        self.assertEqual(projection["current_workers"], [])
        self.assertIsNone(projection["items"][0]["current_stage"])

    def test_terminal_projection_keeps_run_membership_and_terminal_proof_without_active_state(self) -> None:
        completed = _item(1, 2, lifecycle_state="completed")
        completed["routes"]["final"] = _route(
            "available", route="remux", reason="Verified direct publication", source="completed_sidecar"
        )
        completed["terminal_references"] = [
            {
                "kind": "completed",
                "reference": "completed_jobs.jsonl#completed-1",
                "path": r"D:\Library\Collection-0001\Movie-0001.mkv",
                "evidence": {"source": "completed_manifest", "provenance": "terminal", "recorded_at": "2026-07-16T15:00:00Z"},
            }
        ]
        parked = _item(2, 2, lifecycle_state="parked")
        parked["routes"]["final"] = _route("available", route="encode", reason="Destination offline; parked", source="pending_manifest")
        parked["terminal_references"] = [
            {
                "kind": "pending_publish",
                "reference": "pending-manifest-2.json",
                "path": r"C:\Scratch\Pending\Movie-0002.mkv",
                "evidence": {"source": "pending_manifest", "provenance": "terminal", "recorded_at": "2026-07-16T15:00:00Z"},
            }
        ]
        payload = _payload([completed, parked], lifecycle_state="completed")
        payload["run"]["counts"]["completed"] = 1
        payload["run"]["counts"]["parked"] = 1

        projection = project_run_monitor(payload, now=NOW, backend_activity_state="confirmed_idle")

        self.assertEqual(projection["freshness"]["state"], "terminal")
        self.assertEqual(len(projection["items"]), 2)
        self.assertEqual(projection["current_workers"], [])
        self.assertEqual(projection["items"][0]["final_route"]["value"], "remux")
        self.assertEqual(projection["items"][0]["final_route"]["label"], "Final route")
        self.assertEqual(projection["items"][1]["terminal_references"][0]["kind"], "pending_publish")
        self.assertEqual(projection["run"]["counts"]["accepted"], 2)

    def test_terminal_projection_reconciles_legacy_display_name_from_correlated_completed_output(self) -> None:
        item = _item(
            1,
            1,
            lifecycle_state="completed",
            leaf_name="Django.Unchained.2012.1080p.BluRay.x264.YIFY.mp4",
        )
        published_path = r"\\LAYNE-SERVER\Library\Movies\Django Unchained (2012)\Django Unchained (2012).mkv"
        correlated_reference_path = (
            r"\\layne-server\library\Movies\Django Unchained (2012)\.\Django Unchained (2012).mkv"
        )
        item["output"].update(
            {
                "state": "published",
                "published_path": published_path,
                "intended_final_path": published_path,
                "verification_state": "completed",
                "evidence": {
                    "source": "output_evidence",
                    "provenance": "terminal",
                    "recorded_at": "2026-07-16T15:00:00Z",
                },
            }
        )
        item["terminal_references"] = [
            {
                "kind": "completed",
                "reference": published_path,
                "path": correlated_reference_path,
                "evidence": {
                    "source": "completed_artifact",
                    "provenance": "terminal",
                    "recorded_at": "2026-07-16T15:00:01Z",
                },
            }
        ]

        projection = project_run_monitor(
            _payload([item], lifecycle_state="completed"),
            now=NOW,
            backend_activity_state="confirmed_idle",
        )

        self.assertEqual(projection["items"][0]["display_name"], "Django Unchained (2012).mkv")
        self.assertEqual(
            projection["items"][0]["accepted_display_name"],
            "Django.Unchained.2012.1080p.BluRay.x264.YIFY.mp4",
        )
        self.assertEqual(projection["items"][0]["display_name_evidence"]["source"], "completed_artifact")
        self.assertEqual(projection["items"][0]["display_name_evidence"]["provenance"], "terminal")

    def test_terminal_projection_reconciles_legacy_parked_name_and_rejects_mismatched_reference(self) -> None:
        parked = _item(
            1,
            1,
            lifecycle_state="parked",
            leaf_name="Raw.Parked.Release.2026.mkv",
        )
        intended_path = r"\\SERVER\Library\Clean Parked Name (2026)\Clean Parked Name (2026).mkv"
        parked["output"].update(
            {
                "state": "parked",
                "parked_path": r"C:\Scratch\Pending\pending-job-1.mkv",
                "intended_final_path": intended_path,
                "verification_state": "completed",
                "evidence": {
                    "source": "pending_publish_output",
                    "provenance": "terminal",
                    "recorded_at": "2026-07-16T15:00:00Z",
                },
            }
        )
        parked["terminal_references"] = [
            {
                "kind": "pending_publish",
                "reference": "pending-job-1.json",
                "path": r"C:\Scratch\Pending\pending-job-1.json",
                "evidence": {
                    "source": "pending_manifest",
                    "provenance": "terminal",
                    "recorded_at": "2026-07-16T15:00:01Z",
                },
            }
        ]

        parked_projection = project_run_monitor(
            _payload([parked], lifecycle_state="completed"),
            now=NOW,
            backend_activity_state="confirmed_idle",
        )

        self.assertEqual(parked_projection["items"][0]["display_name"], "Clean Parked Name (2026).mkv")
        self.assertEqual(parked_projection["items"][0]["accepted_display_name"], "Raw.Parked.Release.2026.mkv")
        self.assertEqual(parked_projection["items"][0]["display_name_basis"], "terminal_output")
        self.assertEqual(
            parked_projection["items"][0]["display_name_evidence"]["source"],
            "pending_publish_output",
        )

        mismatched = _item(
            1,
            1,
            lifecycle_state="completed",
            leaf_name="Raw.Completed.Release.2026.mkv",
        )
        mismatched["output"].update(
            {
                "state": "published",
                "published_path": r"\\SERVER\Library\Clean Completed Name (2026).mkv",
                "verification_state": "completed",
                "evidence": {
                    "source": "output_evidence",
                    "provenance": "terminal",
                    "recorded_at": "2026-07-16T15:00:00Z",
                },
            }
        )
        mismatched["terminal_references"] = [
            {
                "kind": "completed",
                "reference": r"\\SERVER\Library\Different Name (2026).mkv",
                "path": r"\\SERVER\Library\Different Name (2026).mkv",
                "evidence": {
                    "source": "completed_artifact",
                    "provenance": "terminal",
                    "recorded_at": "2026-07-16T15:00:01Z",
                },
            }
        ]

        mismatched_projection = project_run_monitor(
            _payload([mismatched], lifecycle_state="completed"),
            now=NOW,
            backend_activity_state="confirmed_idle",
        )

        self.assertEqual(mismatched_projection["items"][0]["display_name"], "Raw.Completed.Release.2026.mkv")
        self.assertEqual(mismatched_projection["items"][0]["display_name_basis"], "legacy_accepted")
        self.assertEqual(mismatched_projection["items"][0]["display_name_evidence"]["provenance"], "unknown")

    def test_missing_corrupt_and_partial_new_contracts_fail_honestly_without_legacy_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            state_root = Path(td)
            missing = read_run_monitor_projection(state_root, now=NOW, backend_activity_state="confirmed_idle")
            self.assertEqual(missing["freshness"]["state"], "unavailable")
            self.assertEqual(missing["items"], [])
            self.assertEqual(missing["current_workers"], [])
            self.assertFalse(missing["compatibility"]["legacy_current_work_used"])

            monitor_root = state_root / "RunMonitor"
            monitor_root.mkdir()
            (monitor_root / "latest.json").write_text(
                json.dumps({"schema_version": "pipeline_run_monitor_pointer.v1", "run_id": "partial-run"}),
                encoding="utf-8",
            )
            (monitor_root / "partial-run.json").write_text(
                json.dumps({"schema_version": "pipeline_run_monitor.v1", "run": {"run_id": "partial-run"}}),
                encoding="utf-8",
            )

            partial = read_run_monitor_projection(state_root, now=NOW, backend_activity_state="confirmed_idle")

        self.assertEqual(partial["freshness"]["state"], "unavailable")
        self.assertEqual(partial["freshness"]["reason_code"], "invalid_contract")
        self.assertEqual(partial["items"], [])
        self.assertEqual(partial["current_workers"], [])

    def test_stop_after_current_state_is_backend_owned_and_survives_projection(self) -> None:
        payload = _payload([_item(1, 1, lifecycle_state="active", active_stage="transcode")])
        payload["run"]["lifecycle_state"] = "stop_requested"
        payload["run"]["stop_after_current"] = {
            "state": "requested",
            "requested_at": "2026-07-16T15:00:10Z",
            "evidence": {
                "source": "control_flag",
                "provenance": "backend_confirmed",
                "recorded_at": "2026-07-16T15:00:10Z",
            },
        }

        projection = project_run_monitor(payload, now=NOW, backend_activity_state="confirmed_active")

        self.assertEqual(projection["run"]["lifecycle_state"], "stop_requested")
        self.assertEqual(projection["run"]["stop_after_current"]["state"], "requested")


if __name__ == "__main__":
    unittest.main()
