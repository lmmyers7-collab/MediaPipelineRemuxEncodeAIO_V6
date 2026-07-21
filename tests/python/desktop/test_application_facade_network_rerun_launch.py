from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from mediapipeline.core.processes.rerun_results import rerun_results_payload
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.network.registry import InFlightRegistry
from mediapipeline.desktop.network.rerun_claims import (
    claim_next_network_rerun_row,
    update_network_rerun_row_done,
    update_network_rerun_row_released,
)
from tests.python.desktop.application_facade_network_test_support import (
    _sha256,
    _write_network_worker_result_artifact,
)
from tests.python.desktop.application_facade_test_support import (
    DummyWorkflowFacadeService,
    _resolved,
    write_test_media_file as _media_file,
)


class ApplicationFacadeNetworkRerunLaunchTests(unittest.TestCase):
    def test_network_rerun_start_dry_run_reports_state_files_without_writing(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            source_root = root / "ProfileSource"
            profile_out = root / "ProfileOut"
            handoff_root = root / "NetworkRerunHandoff"
            handoff_root.mkdir()
            movie = source_root / "Movie.mkv"
            movie.parent.mkdir(parents=True)
            movie.write_bytes(b"media")
            csv_path = root / "rerun.csv"
            csv_path.write_text(
                f"enabled,source_path,audit_issue_codes,plex_planned_path\ntrue,{movie},AUDIO,{profile_out / 'Movie.mkv'}\n",
                encoding="utf-8",
            )
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
                "Outsource": str(root / "Outsource"),
                "NetworkRerunHandoffRoot": str(handoff_root),
                "LibraryProfiles": [
                    {
                        "id": "profile",
                        "enabled": True,
                        "source_path": str(source_root),
                        "output_path": str(profile_out),
                    }
                ],
            }
            facade._network_lifecycle_state_commit("coordinator", {"role": "coordinator", "status": "running"})

            result = facade.dry_run_network_rerun_csv_start(
                resolved,
                {"csv_path": str(csv_path), "confirm_replace_final": True, "reason": "operator review"},
            ).to_mapping()

        data = result["data"]
        self.assertTrue(result["ok"])
        self.assertTrue(data["safe_to_apply"])
        self.assertTrue(data["dry_run_only"])
        self.assertEqual(data["effect"], "none")
        self.assertEqual(data["dry_run_writes"], [])
        self.assertFalse(data["touches_media"])
        self.assertFalse(data["writes_queue"])
        self.assertFalse(data["writes_network_state"])
        self.assertFalse(data["launches_work"])
        self.assertEqual(data["preview"]["counts"]["claimable_rows"], 1)
        self.assertEqual(data["preview"]["counts"]["start_ready_rows"], 1)
        self.assertEqual(data["output_handoff"]["status"], "ready")
        self.assertEqual(data["state_files_would_write"][0]["schema_version"], "desktop_rerun_network_batch.v1")
        self.assertIn("command_journal_entry", data["confirmed_route_would_write"])
        self.assertFalse((root / "LocalBase" / "State" / "Rerun" / "Network").exists())
        preconditions = {row["key"]: row for row in data["precondition_results"]}
        self.assertEqual(preconditions["NetworkRole_is_coordinator"]["status"], "pass")
        self.assertEqual(preconditions["coordinator_lifecycle_running"]["status"], "pass")
        self.assertEqual(preconditions["backend_close_readiness_safe"]["status"], "pass")
        self.assertEqual(preconditions["network_preview_has_claimable_rows"]["status"], "pass")
        self.assertEqual(preconditions["network_rerun_handoff_ready"]["status"], "pass")
        self.assertEqual(preconditions["network_rerun_handoff_remote_worker_compatible"]["status"], "review")
        self.assertEqual(preconditions["worker_availability_evidence"]["status"], "review")
        self.assertTrue(data["dry_run_fingerprint"])
        self.assertEqual(preconditions["network_batch_state_path_available"]["status"], "pass")

    def test_network_rerun_start_dry_run_blocks_without_coordinator_role_or_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            movie = _media_file(root, "Movie")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path,audit_issue_codes\ntrue,{movie},AUDIO\n", encoding="utf-8")
            resolved.config_data = {"NetworkRole": "standalone", "Outsource": str(root / "Outsource")}

            result = facade.dry_run_network_rerun_csv_start(
                resolved,
                {"csv_path": str(csv_path), "confirm_replace_final": True, "minimum_worker_count": 1},
            ).to_mapping()

        data = result["data"]
        self.assertFalse(data["safe_to_apply"])
        preconditions = {row["key"]: row for row in data["precondition_results"]}
        self.assertEqual(preconditions["NetworkRole_is_coordinator"]["status"], "blocked")
        self.assertEqual(preconditions["coordinator_lifecycle_running"]["status"], "blocked")
        self.assertEqual(preconditions["worker_availability_evidence"]["status"], "blocked")
        self.assertEqual(data["dry_run_writes"], [])
        self.assertFalse(data["writes_network_state"])

    def test_network_rerun_start_dry_run_blocks_missing_handoff_root(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            movie = _media_file(root, "Movie")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path,audit_issue_codes\ntrue,{movie},AUDIO\n", encoding="utf-8")
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "Outsource": str(root / "Outsource"),
            }
            facade._network_lifecycle_state_commit("coordinator", {"role": "coordinator", "status": "running"})

            result = facade.dry_run_network_rerun_csv_start(
                resolved,
                {"csv_path": str(csv_path), "confirm_replace_final": True},
            ).to_mapping()

        data = result["data"]
        self.assertFalse(data["safe_to_apply"])
        preconditions = {row["key"]: row for row in data["precondition_results"]}
        self.assertEqual(preconditions["network_rerun_handoff_ready"]["status"], "blocked")
        self.assertIn("start_ready_rows=0", preconditions["network_rerun_handoff_ready"]["evidence"])
        self.assertEqual(data["output_handoff"]["status"], "not_configured")
        self.assertIn("network_rerun_handoff_not_ready", data["preview"]["start_blockers"])
        self.assertFalse((root / "LocalBase" / "State" / "Rerun" / "Network").exists())

    def test_network_rerun_start_writes_claim_enabled_batch_state_and_strict_journal(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            source_root = root / "ProfileSource"
            profile_out = root / "ProfileOut"
            handoff_root = root / "NetworkRerunHandoff"
            handoff_root.mkdir()
            movie = source_root / "Movie.mkv"
            movie.parent.mkdir(parents=True)
            movie.write_bytes(b"media")
            csv_path = root / "rerun.csv"
            csv_path.write_text(
                f"enabled,source_path,audit_issue_codes,plex_planned_path\ntrue,{movie},AUDIO,{profile_out / 'Movie.mkv'}\n",
                encoding="utf-8",
            )
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
                "Outsource": str(root / "Outsource"),
                "NetworkRerunHandoffRoot": str(handoff_root),
                "LibraryProfiles": [
                    {
                        "id": "profile",
                        "enabled": True,
                        "source_path": str(source_root),
                        "output_path": str(profile_out),
                    }
                ],
            }
            facade._network_lifecycle_state_commit("coordinator", {"role": "coordinator", "status": "running"})
            request = {"csv_path": str(csv_path), "confirm_replace_final": True, "reason": "operator review"}
            dry_run = facade.dry_run_network_rerun_csv_start(resolved, request).to_mapping()
            journal: list[dict[str, object]] = []

            result = facade.start_network_rerun_csv_batch(
                resolved,
                {**request, "dry_run_fingerprint": dry_run["data"]["dry_run_fingerprint"], "confirm_start": True},
                journal_recorder=lambda payload, request_body: journal.append({"payload": payload, "request": request_body}),
            ).to_mapping()

            state_path = Path(result["data"]["state_file"]["path"])
            state = json.loads(state_path.read_text(encoding="utf-8"))

        self.assertTrue(result["ok"])
        self.assertEqual(result["command"], "rerun.network.start")
        self.assertTrue(result["data"]["strict_command_journal_recorded"])
        self.assertTrue(result["data"]["state_written"])
        self.assertTrue(result["data"]["writes_network_state"])
        self.assertFalse(result["data"]["touches_media"])
        self.assertFalse(result["data"]["writes_queue"])
        self.assertFalse(result["data"]["launches_work"])
        self.assertEqual(len(journal), 1)
        self.assertEqual(journal[0]["payload"]["command"], "rerun.network.start")
        self.assertEqual(state["schema_version"], "desktop_rerun_network_batch.v1")
        self.assertEqual(state["status"], "active")
        self.assertTrue(state["claim_provider_enabled"])
        self.assertTrue(state["worker_execution_enabled"])
        self.assertTrue(state["rows_claimable"])
        self.assertEqual(state["phase"], "phase_4b_csv_row_claim_execution")
        self.assertEqual(state["output_handoff"]["status"], "ready")
        self.assertEqual(state["handoff_probe"]["status"], "pass")
        self.assertEqual(state["row_count"], 1)
        self.assertTrue(state["rows"][0]["claimable"])
        self.assertEqual(state["rows"][0]["status"], "pending_claim")
        self.assertEqual(state["rows"][0]["claim_status"], "pending_claim")
        self.assertTrue(state["rows"][0]["planned_output_path"].endswith(state["rows"][0]["row_key"]))
        self.assertEqual(state["rows"][0]["output_handoff"]["batch_id"], state["batch_id"])

    def test_network_rerun_phase8_start_claim_done_destination_and_read_model(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            source_root = root / "ProfileSource"
            profile_out = root / "ProfileOut"
            outsource = root / "Outsource"
            handoff_root = root / "NetworkRerunHandoff"
            handoff_root.mkdir()
            movie = source_root / "Phase8.Movie.2026.mkv"
            movie.parent.mkdir(parents=True)
            movie.write_bytes(b"phase8-source-media")
            source_hash_before = _sha256(movie)
            final_output = profile_out / "Phase8 Movie (2026).mkv"
            csv_path = root / "phase8-rerun.csv"
            csv_path.write_text(
                "enabled,source_path,audit_issue_codes,plex_planned_path,"
                "source_identity_v2,source_identity_v2_algorithm,"
                "source_content_sha256,source_content_sha256_algorithm\n"
                f"true,{movie},AUDIO,{final_output},{source_hash_before},sha256,"
                f"{source_hash_before},sha256-full-file\n",
                encoding="utf-8",
            )
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
                "Outsource": str(outsource),
                "NetworkRerunHandoffRoot": str(handoff_root),
                "LibraryProfiles": [
                    {
                        "id": "profile",
                        "enabled": True,
                        "source_path": str(source_root),
                        "output_path": str(profile_out),
                    }
                ],
            }
            facade._network_lifecycle_state_commit("coordinator", {"role": "coordinator", "status": "running"})
            request = {
                "csv_path": str(csv_path),
                "destination_mode": "pending_publish",
                "collision_policy": "suffix",
                "reason": "phase8 end-to-end validation",
            }
            dry_run = facade.dry_run_network_rerun_csv_start(resolved, request).to_mapping()
            journal: list[dict[str, object]] = []

            start = facade.start_network_rerun_csv_batch(
                resolved,
                {**request, "dry_run_fingerprint": dry_run["data"]["dry_run_fingerprint"], "confirm_start": True},
                journal_recorder=lambda payload, request_body: journal.append({"payload": payload, "request": request_body}),
            ).to_mapping()

            state_path = Path(start["data"]["state_file"]["path"])
            app = SimpleNamespace(resolved=resolved, product_version="v5-test")
            registry = InFlightRegistry()
            first_lease = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-phase8-a",
                worker_name="Phase 8 Worker A",
                accessible_library_ids=["profile"],
                encode_config_for_row=lambda record: {"record_source": str(record.source_path)},
                allow_local_handoff=True,
                job_id="phase8-release",
            )
            assert first_lease is not None
            duplicate = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-phase8-b",
                worker_name="Phase 8 Worker B",
                accessible_library_ids=["profile"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=True,
                job_id="phase8-duplicate",
            )
            released = registry.unclaim(first_lease.response.job_id, "worker-phase8-a")
            assert released is not None
            update_network_rerun_row_released(app=app, job=released, worker_id="worker-phase8-a", reason="phase8 restart")
            with registry._lock:
                registry._recent_completions.clear()
            second_lease = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-phase8-b",
                worker_name="Phase 8 Worker B",
                accessible_library_ids=["profile"],
                encode_config_for_row=lambda record: {"record_source": str(record.source_path)},
                allow_local_handoff=True,
                job_id="phase8-complete",
            )
            assert second_lease is not None
            output_path = Path(second_lease.response.planned_output_path) / "Phase8 Movie (2026).mkv"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"phase8-worker-output")
            artifact_path = _write_network_worker_result_artifact(
                root,
                job_id=second_lease.response.job_id,
                output_path=output_path,
                batch_id=str(second_lease.response.rerun_batch_id),
                row_key=str(second_lease.response.rerun_row_key),
            )
            completed = registry.complete(second_lease.response.job_id, "worker-phase8-b", success=True)
            assert completed is not None
            update_network_rerun_row_done(
                app=app,
                job=completed,
                request=SimpleNamespace(
                    job_id=second_lease.response.job_id,
                    worker_id="worker-phase8-b",
                    success=True,
                    output_path=str(output_path),
                    output_size_bytes=output_path.stat().st_size,
                    completion_status="processed",
                    publish_state="published",
                    publish_mode="handoff",
                    route="network_lifecycle_single_file",
                    reason_code="",
                    reason="",
                    error_message="",
                    queue_terminal=False,
                    retry_on_failure=True,
                    worker_result_artifact_path=str(artifact_path),
                ),
            )

            state = json.loads(state_path.read_text(encoding="utf-8"))
            row = state["rows"][0]
            results = rerun_results_payload(resolved, service=service, limit=24)
            network_rows = [item for item in results["rows"] if item.get("queue_source") == "network_csv_rerun"]
            terminal_claim = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-phase8-c",
                worker_name="Phase 8 Worker C",
                accessible_library_ids=["profile"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=True,
                job_id="phase8-after-terminal",
            )
            source_hash_after = _sha256(movie)
            output_exists_after = output_path.exists()
            final_output_exists_after = final_output.exists()
            pending_manifest_exists = Path(row["pending_publish_manifest_path"]).is_file()
            pending_payload_path = Path(row["pending_publish_payload_path"])
            pending_payload_exists = pending_payload_path.is_file()
            pending_payload_bytes = pending_payload_path.read_bytes() if pending_payload_exists else b""

        self.assertTrue(dry_run["ok"])
        self.assertTrue(dry_run["data"]["safe_to_apply"])
        self.assertTrue(start["ok"])
        self.assertEqual(len(journal), 1)
        self.assertEqual(journal[0]["payload"]["command"], "rerun.network.start")
        self.assertEqual(first_lease.response.job_kind, "csv_rerun_row")
        self.assertEqual(
            first_lease.response.source_identity["source_content_sha256"],
            source_hash_before,
        )
        self.assertIsNone(duplicate)
        self.assertEqual(second_lease.response.job_kind, "csv_rerun_row")
        self.assertEqual(row["status"], "pending_publish")
        self.assertFalse(row["claimable"])
        self.assertEqual(row["destination_policy_result"]["status"], "pending_publish")
        self.assertTrue(row["destination_policy_result"]["ok"])
        self.assertTrue(row["destination_policy_applied"])
        self.assertEqual(row["reducer_result"]["classification"], "success")
        self.assertEqual(source_hash_after, source_hash_before)
        self.assertFalse(output_exists_after)
        self.assertFalse(final_output_exists_after)
        self.assertTrue(pending_manifest_exists)
        self.assertTrue(pending_payload_exists)
        self.assertEqual(pending_payload_bytes, b"phase8-worker-output")
        self.assertEqual(len(network_rows), 1)
        self.assertEqual(network_rows[0]["queue_status"], "pending_publish")
        self.assertTrue(network_rows[0]["destination_state"]["destination_policy_applied"])
        self.assertEqual(network_rows[0]["destination_state"]["destination_policy_status"], "pending_publish")
        self.assertTrue(results["queue_state"]["contains_network_csv_rerun"])
        self.assertIsNone(terminal_claim)

    def test_network_rerun_start_rejects_stale_dry_run_fingerprint_without_writing_state(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            movie = _media_file(root, "Movie")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path,audit_issue_codes\ntrue,{movie},AUDIO\n", encoding="utf-8")
            handoff_root = root / "NetworkRerunHandoff"
            handoff_root.mkdir()
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "Outsource": str(root / "Outsource"),
                "NetworkRerunHandoffRoot": str(handoff_root),
            }
            facade._network_lifecycle_state_commit("coordinator", {"role": "coordinator", "status": "running"})

            result = facade.start_network_rerun_csv_batch(
                resolved,
                {
                    "csv_path": str(csv_path),
                    "confirm_replace_final": True,
                    "dry_run_fingerprint": "stale",
                    "confirm_start": True,
                },
                journal_recorder=lambda _payload, _request: None,
            ).to_mapping()

        self.assertFalse(result["ok"])
        self.assertIn("dry_run_fingerprint_mismatch", result["errors"])
        self.assertFalse((root / "LocalBase" / "State" / "Rerun" / "Network").exists())

    def test_network_rerun_start_cleans_batch_state_when_strict_journal_fails(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            movie = _media_file(root, "Movie")
            csv_path = root / "rerun.csv"
            csv_path.write_text(f"enabled,source_path,audit_issue_codes\ntrue,{movie},AUDIO\n", encoding="utf-8")
            handoff_root = root / "NetworkRerunHandoff"
            handoff_root.mkdir()
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "Outsource": str(root / "Outsource"),
                "NetworkRerunHandoffRoot": str(handoff_root),
            }
            facade._network_lifecycle_state_commit("coordinator", {"role": "coordinator", "status": "running"})
            request = {"csv_path": str(csv_path), "confirm_replace_final": True}
            dry_run = facade.dry_run_network_rerun_csv_start(resolved, request).to_mapping()

            def failing_journal(_payload: dict[str, object], _request: dict[str, object] | None) -> None:
                raise RuntimeError("journal unavailable")

            result = facade.start_network_rerun_csv_batch(
                resolved,
                {**request, "dry_run_fingerprint": dry_run["data"]["dry_run_fingerprint"], "confirm_start": True},
                journal_recorder=failing_journal,
            ).to_mapping()
            state_path = Path(result["data"]["state_file"]["path"])

        self.assertFalse(result["ok"])
        self.assertIn("command_journal_write_failed", result["errors"][0])
        self.assertIn("state_cleanup_ok", result["data"]["cleanup_result"])
        self.assertFalse(state_path.exists())
        self.assertFalse(result["data"]["writes_network_state"])


if __name__ == "__main__":
    unittest.main()
