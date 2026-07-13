from __future__ import annotations

import json
import tempfile
import threading
import unittest
from pathlib import Path
from types import SimpleNamespace

from mediapipeline.core.kernel.models import ResolvedPaths
from mediapipeline.desktop.network.coordinator import CoordinatorDispatcher
from mediapipeline.desktop.network.processing_policy import materialize_worker_effective_config
from mediapipeline.desktop.network.protocol import ClaimResponse, DoneRequest
from mediapipeline.desktop.network.registry import InFlightRegistry
from mediapipeline.desktop.network.rerun_claims import (
    claim_next_network_rerun_row,
    record_late_network_rerun_row_done,
    update_network_rerun_row_done,
    update_network_rerun_row_released,
)
from mediapipeline.desktop.network.worker_loops import _probe_csv_rerun_handoff


def _state_payload(
    root: Path,
    *,
    source: Path,
    remote_compatible: bool = True,
    destination_policy_enabled: bool = False,
    destination_mode: str = "auto_replace_clean_else_pending_review",
    final_output: Path | None = None,
    replacement_eligible: bool = False,
    confirm_replace_final: bool = False,
    confirm_source_overwrite: bool = False,
) -> dict[str, object]:
    handoff_path = root / "Handoff" / "batch-1" / "row-1"
    row: dict[str, object] = {
        "schema_version": "desktop_rerun_network_batch_row.v1",
        "row_key": "row-1",
        "row_index": 2,
        "source_path": str(source),
        "planned_output_path": str(handoff_path),
        "library_id": "movies",
        "status": "pending_claim",
        "claimable": True,
        "claim_status": "pending_claim",
        "source_mapping": {
            "method": "library_id_relative_path",
            "library_id": "movies",
            "relative_path": "Movie.mkv",
        },
        "output_handoff": {
            "ready": True,
            "remote_worker_compatible": remote_compatible,
            "planned_row_handoff_path": str(handoff_path),
        },
    }
    if destination_policy_enabled:
        row.update(
            {
                "source_size": source.stat().st_size if source.exists() else 0,
                "source_mtime_utc": "2026-07-06T00:00:00Z",
                "source_identity_v2": f"network-test:{source.name}",
                "source_identity_v2_algorithm": "test-fixture",
                "media_kind": "movie",
                "audit_issue_codes": "audio-policy",
                "final_output_path": str(final_output or (root / "Outsource" / source.name)),
                "final_output_source": "csv_completed_output",
                "final_output_source_field": "plex_planned_path",
                "rerun_rule_destination_behavior": destination_mode,
                "rerun_rule_replacement_eligible": replacement_eligible,
                "destination_policy": {
                    "destination_behavior": destination_mode,
                    "replacement_eligible": replacement_eligible,
                },
            }
        )
    payload: dict[str, object] = {
        "schema_version": "desktop_rerun_network_batch.v1",
        "batch_id": "batch-1",
        "status": "active",
        "claim_provider_enabled": True,
        "worker_execution_enabled": True,
        "rows_claimable": True,
        "rows": [row],
    }
    if destination_policy_enabled:
        payload.update(
            {
                "phase": "phase_6_destination_policy_integration",
                "destination_policy_application_enabled": True,
                "destination_mode": destination_mode,
                "collision_policy": "replace_final" if destination_mode == "publish_replace_final" else "suffix",
                "confirm_replace_final": confirm_replace_final,
                "confirm_source_overwrite": confirm_source_overwrite,
                "request_summary": {
                    "confirm_replace_final": confirm_replace_final,
                    "confirm_source_overwrite": confirm_source_overwrite,
                },
            }
        )
    return payload


def _resolved_paths(root: Path) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "MediaPipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "Audit.ps1",
        rerun_script_path=root / "Rerun.ps1",
        powershell_host="pwsh",
        local_base=root / "LocalBase",
        state_root=root / "State",
        pending_push_path=root / "State" / "PendingServerPush",
        config_data={
            "Outsource": str(root / "Outsource"),
            "LibraryProfiles": [
                {
                    "id": "movies",
                    "source_path": str(root / "Movies"),
                    "output_path": str(root / "Outsource"),
                }
            ],
        },
    )


def _request_for_worker_done(*, job_id: str, output_path: Path, artifact_path: Path) -> SimpleNamespace:
    return SimpleNamespace(
        job_id=job_id,
        worker_id="worker-1",
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
    )


def _run_destination_policy(
    root: Path,
    *,
    destination_mode: str,
    final_output: Path | None = None,
    replacement_eligible: bool = False,
    confirm_replace_final: bool = False,
) -> SimpleNamespace:
    source = root / "Movies" / "Movie.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"source")
    resolved = _resolved_paths(root)
    state_path = _write_batch(
        root,
        _state_payload(
            root,
            source=source,
            destination_policy_enabled=True,
            destination_mode=destination_mode,
            final_output=final_output or (root / "Outsource" / "Movie.mkv"),
            replacement_eligible=replacement_eligible,
            confirm_replace_final=confirm_replace_final,
        ),
    )
    app = SimpleNamespace(resolved=resolved, product_version="test-version")
    registry = InFlightRegistry()
    lease = claim_next_network_rerun_row(
        app=app,
        registry=registry,
        worker_id="worker-1",
        worker_name="Worker",
        accessible_library_ids=["movies"],
        encode_config_for_row=lambda _record: {},
        allow_local_handoff=False,
        job_id=f"job-{destination_mode}",
    )
    assert lease is not None
    completed = registry.complete(lease.response.job_id, "worker-1", success=True)
    assert completed is not None
    output_path = root / "Handoff" / "batch-1" / "row-1" / "Movie.mkv"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(b"handoff-output")
    artifact_path = _write_worker_result_artifact(root, job_id=lease.response.job_id, output_path=output_path)

    update_network_rerun_row_done(
        app=app,
        job=completed,
        request=_request_for_worker_done(job_id=lease.response.job_id, output_path=output_path, artifact_path=artifact_path),
    )

    state = json.loads(state_path.read_text(encoding="utf-8"))
    return SimpleNamespace(
        root=root,
        resolved=resolved,
        source=source,
        output_path=output_path,
        final_output=final_output or (root / "Outsource" / "Movie.mkv"),
        state_path=state_path,
        state=state,
        row=state["rows"][0],
    )


def _write_batch(root: Path, payload: dict[str, object]) -> Path:
    path = root / "State" / "Rerun" / "Network" / "batch-1.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_worker_result_artifact(
    root: Path,
    *,
    job_id: str,
    output_path: Path,
    batch_id: str = "batch-1",
    row_key: str = "row-1",
    success: bool = True,
    status: str = "processed",
    publish_state: str = "published",
    route: str = "network_lifecycle_single_file",
    schema_version: str = "local_worker_result.v1",
) -> Path:
    path = root / "State" / "NetworkWorkerResults" / job_id / "worker_result.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "SchemaVersion": schema_version,
                "JobKind": "csv_rerun_row",
                "RerunBatchId": batch_id,
                "RerunRowKey": row_key,
                "WorkerClaimId": job_id,
                "WorkerRunId": "run-1",
                "Success": success,
                "Status": status,
                "OutputPath": str(output_path),
                "OutputSizeBytes": output_path.stat().st_size if output_path.exists() else 0,
                "PublishState": publish_state,
                "PublishMode": "handoff",
                "Route": route,
            }
        ),
        encoding="utf-8",
    )
    return path


def _claim_row_for_reducer(root: Path, *, job_id: str = "job-reducer") -> tuple[SimpleNamespace, Path, object, Path, Path]:
    source = root / "Movies" / "Movie.mkv"
    source.parent.mkdir(parents=True, exist_ok=True)
    source.write_bytes(b"source")
    state_path = _write_batch(root, _state_payload(root, source=source))
    app = SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State"))
    registry = InFlightRegistry()
    lease = claim_next_network_rerun_row(
        app=app,
        registry=registry,
        worker_id="worker-1",
        worker_name="Worker",
        accessible_library_ids=["movies"],
        encode_config_for_row=lambda _record: {},
        allow_local_handoff=False,
        job_id=job_id,
    )
    assert lease is not None
    completed = registry.complete(job_id, "worker-1", success=True)
    assert completed is not None
    output_path = root / "Handoff" / "batch-1" / "row-1" / "Movie.mkv"
    return app, state_path, completed, source, output_path


class NetworkRerunClaimTests(unittest.TestCase):
    def test_http_claim_and_done_updates_network_rerun_row_pending_reduction(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir()
            source.write_bytes(b"source")
            state_path = _write_batch(root, _state_payload(root, source=source))
            app = SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State"), queue_records=[])
            registry = InFlightRegistry()
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._app = app
            dispatcher._registry = registry
            dispatcher._claim_lock = threading.Lock()
            dispatcher._accepting_claims = True
            dispatcher._inflight_state_path = lambda: root / "State" / "coordinator_inflight.json"  # type: ignore[method-assign]
            dispatcher._compute_retry_after_seconds = lambda: 5  # type: ignore[method-assign]
            dispatcher._coordinator_max_job_retries = lambda: 3  # type: ignore[method-assign]
            dispatcher._source_has_prior_failure = lambda _source_path: False  # type: ignore[method-assign]
            dispatcher._snapshot_encode_config = lambda _worker_name, record=None: {"source": str(getattr(record, "source_path", ""))}  # type: ignore[method-assign]
            dispatcher._scan_for_next_record = lambda *_args, **_kwargs: (None, {})  # type: ignore[method-assign]
            dispatcher._safe_log_cluster_event = lambda *_args, **_kwargs: None  # type: ignore[method-assign]

            claim_sent: list[tuple[dict[str, object], int]] = []
            claim_handler = SimpleNamespace(_send_json=lambda payload, status=200: claim_sent.append((payload, status)))
            CoordinatorDispatcher._http_claim(
                dispatcher,
                claim_handler,
                {"worker_id": "worker-1", "worker_name": "Worker", "accessible_library_ids": "movies"},
            )

            self.assertEqual(claim_sent[0][1], 200)
            claim_payload = claim_sent[0][0]
            self.assertEqual(claim_payload["job_kind"], "csv_rerun_row")
            self.assertEqual(claim_payload["rerun_row_key"], "row-1")
            self.assertTrue(registry.is_in_flight(str(source)))

            output_path = root / "Handoff" / "batch-1" / "row-1" / "Movie.mkv"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"handoff-output")
            artifact_path = _write_worker_result_artifact(root, job_id=str(claim_payload["job_id"]), output_path=output_path)
            done = DoneRequest(
                job_id=str(claim_payload["job_id"]),
                worker_id="worker-1",
                success=True,
                output_path=str(output_path),
                output_size_bytes=output_path.stat().st_size,
                completion_status="processed",
                publish_state="published",
                publish_mode="handoff",
                route="network_lifecycle_single_file",
                job_kind="csv_rerun_row",
                rerun_batch_id="batch-1",
                rerun_row_key="row-1",
                planned_output_path=str(output_path.parent),
                source_identity=claim_payload["source_identity"],
                coordinator_source_path=str(source),
                worker_source_path=str(source),
                worker_result_artifact_path=str(artifact_path),
            )
            done_sent: list[tuple[dict[str, object], int]] = []
            done_handler = SimpleNamespace(_send_json=lambda payload, status=200: done_sent.append((payload, status)))
            CoordinatorDispatcher._http_done(dispatcher, done_handler, json.dumps(done.to_dict()).encode("utf-8"))

            self.assertEqual(done_sent[0], ({"status": "ok", "row_status": "pending_reduction"}, 200))
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["rows"][0]["status"], "worker_completed_pending_reduction")
            self.assertFalse(state["rows"][0]["worker_result"]["destination_policy_applied"])
            self.assertEqual(state["rows"][0]["reducer_result"]["classification"], "success")
            self.assertTrue(state["rows"][0]["reducer_result"]["pending_destination_policy"])
            self.assertEqual(state["rows"][0]["verified_output_path"], str(output_path))

    def test_claim_next_network_rerun_row_claims_one_row_and_blocks_duplicate_source(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir()
            source.write_bytes(b"source")
            state_path = _write_batch(root, _state_payload(root, source=source))
            app = SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State"))
            registry = InFlightRegistry()

            lease = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-1",
                worker_name="Worker",
                accessible_library_ids=["movies"],
                encode_config_for_row=lambda record: {"record_source": str(record.source_path)},
                allow_local_handoff=False,
                job_id="job-1",
            )

            self.assertIsNotNone(lease)
            assert lease is not None
            self.assertEqual(lease.response.job_kind, "csv_rerun_row")
            self.assertEqual(lease.response.rerun_batch_id, "batch-1")
            self.assertEqual(lease.response.rerun_row_key, "row-1")
            self.assertEqual(lease.response.library_id, "movies")
            self.assertEqual(lease.response.relative_path, "Movie.mkv")
            self.assertTrue(registry.is_in_flight(str(source)))

            state = json.loads(state_path.read_text(encoding="utf-8"))
            row = state["rows"][0]
            self.assertEqual(row["status"], "claimed")
            self.assertFalse(row["claimable"])
            self.assertEqual(row["active_claim"]["job_id"], "job-1")

            duplicate = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-2",
                worker_name="Worker Two",
                accessible_library_ids=["movies"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=False,
            )
            self.assertIsNone(duplicate)

    def test_local_claim_next_returns_network_rerun_job(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir()
            source.write_bytes(b"source")
            state_path = _write_batch(root, _state_payload(root, source=source))
            inflight_path = root / "State" / "coordinator_inflight.json"
            app = SimpleNamespace(
                resolved=SimpleNamespace(state_root=root / "State"),
                _machine_id="coordinator-1",
            )
            registry = InFlightRegistry()
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._app = app
            dispatcher._registry = registry
            dispatcher._claim_lock = threading.Lock()
            dispatcher._config = lambda: {"CoordinatorAlsoEncodeLocally": True}  # type: ignore[method-assign]
            dispatcher._snapshot_encode_config = (  # type: ignore[method-assign]
                lambda _worker_name, record=None: {
                    "preset": "copy",
                    "source": str(getattr(record, "source_path", "")),
                }
            )
            dispatcher._inflight_state_path = lambda: inflight_path  # type: ignore[method-assign]

            claimed = dispatcher.claim_next()

            self.assertIsNotNone(claimed)
            assert claimed is not None
            self.assertEqual(claimed.worker_id, "coordinator-1")
            self.assertEqual(claimed.record.source_path, source)
            self.assertEqual(claimed.record.library_id, "movies")
            self.assertEqual(claimed.record.route_name, "network_csv_rerun_row")
            self.assertEqual(claimed.encode_config["preset"], "copy")
            self.assertEqual(claimed.encode_config["source"], str(source))
            self.assertEqual(claimed.encode_config["__job_kind"], "csv_rerun_row")
            self.assertTrue(registry.is_in_flight(str(source)))
            self.assertTrue(inflight_path.exists())
            self.assertEqual(
                json.loads(inflight_path.read_text(encoding="utf-8"))["jobs"][0]["job_id"],
                claimed.job_id,
            )
            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(row["status"], "claimed")
            self.assertEqual(row["active_claim"]["worker_id"], "coordinator-1")

    def test_remote_claim_skips_local_only_handoff_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir()
            source.write_bytes(b"source")
            _write_batch(root, _state_payload(root, source=source, remote_compatible=False))
            app = SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State"))

            self.assertIsNone(
                claim_next_network_rerun_row(
                    app=app,
                    registry=InFlightRegistry(),
                    worker_id="worker-1",
                    worker_name="Worker",
                    accessible_library_ids=["movies"],
                    encode_config_for_row=lambda _record: {},
                    allow_local_handoff=False,
                )
            )

    def test_release_and_done_update_batch_row_without_final_destination_policy(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir()
            source.write_bytes(b"source")
            state_path = _write_batch(root, _state_payload(root, source=source))
            app = SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State"))
            registry = InFlightRegistry()

            lease = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-1",
                worker_name="Worker",
                accessible_library_ids=["movies"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=False,
                job_id="job-release",
            )
            assert lease is not None
            released = registry.unclaim("job-release", "worker-1")
            self.assertIsNotNone(released)
            update_network_rerun_row_released(app=app, job=released, worker_id="worker-1", reason="test")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["rows"][0]["status"], "pending_claim")
            self.assertTrue(state["rows"][0]["claimable"])
            with registry._lock:
                registry._recent_completions.clear()

            lease = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-1",
                worker_name="Worker",
                accessible_library_ids=["movies"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=False,
                job_id="job-done",
            )
            assert lease is not None
            completed = registry.complete("job-done", "worker-1", success=True)
            self.assertIsNotNone(completed)
            output_path = root / "Handoff" / "batch-1" / "row-1" / "Movie.mkv"
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"handoff-output")
            artifact_path = _write_worker_result_artifact(root, job_id="job-done", output_path=output_path)
            request = SimpleNamespace(
                job_id="job-done",
                worker_id="worker-1",
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
            )
            update_network_rerun_row_done(app=app, job=completed, request=request)

            state = json.loads(state_path.read_text(encoding="utf-8"))
            row = state["rows"][0]
            self.assertEqual(row["status"], "worker_completed_pending_reduction")
            self.assertFalse(row["claimable"])
            self.assertFalse(row["worker_result"]["destination_policy_applied"])
            self.assertTrue(row["worker_result"]["pending_reduction"])
            self.assertEqual(row["reducer_result"]["classification"], "success")
            self.assertTrue(row["reducer_result"]["output_artifact"]["under_planned_handoff"])

    def test_destination_policy_promotes_network_output_to_pending_publish(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = _run_destination_policy(Path(td), destination_mode="pending_publish")

            row = result.row
            pending_payload = Path(row["pending_publish_payload_path"])
            pending_manifest = Path(row["pending_publish_manifest_path"])
            self.assertEqual(row["status"], "pending_publish")
            self.assertFalse(row["reducer_result"]["pending_destination_policy"])
            self.assertTrue(row["destination_policy_applied"])
            self.assertTrue(row["destination_policy_result"]["ok"])
            self.assertEqual(row["destination_policy_result"]["status"], "pending_publish")
            self.assertEqual(row["server_out"], str(result.final_output))
            self.assertEqual(result.source.read_bytes(), b"source")
            self.assertFalse(result.output_path.exists())
            self.assertTrue(pending_payload.is_file())
            self.assertEqual(pending_payload.read_bytes(), b"handoff-output")
            manifest = json.loads(pending_manifest.read_text(encoding="utf-8"))
            self.assertEqual(manifest["manifest_state"], "parked")
            self.assertEqual(manifest["server_out"], str(result.final_output))
            self.assertEqual(manifest["source_path"], str(result.source))

    def test_destination_policy_leaves_network_output_in_review_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            result = _run_destination_policy(Path(td), destination_mode="review_workspace")

            row = result.row
            self.assertEqual(row["status"], "review_workspace")
            self.assertEqual(row["review_output_path"], str(result.output_path))
            self.assertTrue(row["destination_policy_result"]["ok"])
            self.assertEqual(row["destination_policy_result"]["status"], "review_workspace")
            self.assertEqual(result.source.read_bytes(), b"source")
            self.assertTrue(result.output_path.is_file())
            self.assertFalse((result.resolved.pending_push_path / "Movie.mkv").exists())

    def test_destination_policy_copies_network_output_to_non_overlapping_final_path(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            final_output = root / "Outsource" / "Movie.mkv"
            final_output.parent.mkdir(parents=True, exist_ok=True)
            final_output.write_bytes(b"existing-final")

            result = _run_destination_policy(root, destination_mode="publish_non_overlap", final_output=final_output)

            row = result.row
            published_path = Path(row["published_path"])
            self.assertEqual(row["status"], "published_non_overlap")
            self.assertNotEqual(published_path, final_output)
            self.assertTrue(published_path.name.startswith("Movie.network-rerun-row-1"))
            self.assertEqual(published_path.read_bytes(), b"handoff-output")
            self.assertEqual(final_output.read_bytes(), b"existing-final")
            self.assertEqual(result.source.read_bytes(), b"source")
            self.assertTrue(result.output_path.is_file())

    def test_destination_policy_replaces_final_path_only_with_batch_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            final_output = root / "Outsource" / "Movie.mkv"
            final_output.parent.mkdir(parents=True, exist_ok=True)
            final_output.write_bytes(b"existing-final")

            result = _run_destination_policy(
                root,
                destination_mode="publish_replace_final",
                final_output=final_output,
                confirm_replace_final=True,
            )

            row = result.row
            self.assertEqual(row["status"], "published_replace_final")
            self.assertEqual(row["published_path"], str(final_output))
            self.assertEqual(final_output.read_bytes(), b"handoff-output")
            self.assertEqual(result.source.read_bytes(), b"source")
            self.assertTrue(result.output_path.is_file())
            self.assertIn(str(final_output), row["destination_policy_result"]["overwritten_files"])

    def test_destination_policy_failure_preserves_source_and_handoff_output(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            outside_final = root / "Outside" / "Movie.mkv"

            result = _run_destination_policy(root, destination_mode="publish_non_overlap", final_output=outside_final)

            row = result.row
            self.assertEqual(row["status"], "destination_policy_failed")
            self.assertFalse(row["destination_policy_applied"])
            self.assertFalse(row["reducer_result"]["pending_destination_policy"])
            self.assertTrue(row["destination_policy_result"]["terminal"])
            self.assertIn("rerun_final_output_outside_configured_root", row["destination_policy_result"]["errors"])
            self.assertEqual(result.source.read_bytes(), b"source")
            self.assertTrue(result.output_path.is_file())
            self.assertFalse(outside_final.exists())

    def test_reducer_classifies_success_output_missing_and_corrupt_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app, state_path, completed, _source, missing_output = _claim_row_for_reducer(root, job_id="job-missing")
            artifact_path = _write_worker_result_artifact(root, job_id="job-missing", output_path=missing_output)
            request = SimpleNamespace(
                job_id="job-missing",
                worker_id="worker-1",
                success=True,
                output_path=str(missing_output),
                output_size_bytes=0,
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
            )

            update_network_rerun_row_done(app=app, job=completed, request=request)

            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(row["status"], "worker_failed_pending_reduction")
            self.assertEqual(row["reducer_result"]["classification"], "output_missing")
            self.assertTrue(row["reducer_result"]["retryable"])

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app, state_path, completed, _source, output_path = _claim_row_for_reducer(root, job_id="job-corrupt")
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"handoff-output")
            artifact_path = _write_worker_result_artifact(root, job_id="job-corrupt", output_path=output_path, row_key="wrong-row")
            request = SimpleNamespace(
                job_id="job-corrupt",
                worker_id="worker-1",
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
            )

            update_network_rerun_row_done(app=app, job=completed, request=request)

            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(row["status"], "worker_failed_pending_reduction")
            self.assertEqual(row["reducer_result"]["classification"], "corrupt_result")
            self.assertIn("artifact_row_key_mismatch", row["reducer_result"]["mismatches"])

    def test_reducer_classifies_failure_duplicate_and_late_done_reports(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app, state_path, completed, _source, _output_path = _claim_row_for_reducer(root, job_id="job-failed")
            request = SimpleNamespace(
                job_id="job-failed",
                worker_id="worker-1",
                success=False,
                output_path="",
                output_size_bytes=0,
                completion_status="failed",
                publish_state="",
                publish_mode="",
                route="network_lifecycle_single_file",
                reason_code="ENCODE_ERROR",
                reason="transcode failed",
                error_message="",
                queue_terminal=False,
                retry_on_failure=True,
                worker_result_artifact_path="",
            )

            update_network_rerun_row_done(app=app, job=completed, request=request)
            update_network_rerun_row_done(app=app, job=completed, request=request)

            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(row["status"], "worker_failed_pending_reduction")
            self.assertEqual(row["reducer_result"]["classification"], "failed_retryable")
            self.assertEqual(row["duplicate_done_count"], 1)

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app, state_path, completed, _source, _output_path = _claim_row_for_reducer(root, job_id="job-terminal")
            request = SimpleNamespace(
                job_id="job-terminal",
                worker_id="worker-1",
                success=False,
                output_path="",
                output_size_bytes=0,
                completion_status="manual_review",
                publish_state="",
                publish_mode="",
                route="network_lifecycle_single_file",
                reason_code="MANUAL_REVIEW",
                reason="terminal review",
                error_message="",
                queue_terminal=True,
                retry_on_failure=True,
                worker_result_artifact_path="",
            )

            update_network_rerun_row_done(app=app, job=completed, request=request)

            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(row["reducer_result"]["classification"], "failed_terminal")
            self.assertTrue(row["reducer_result"]["terminal"])
            self.assertFalse(row["reducer_result"]["retryable"])

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"source")
            state_path = _write_batch(root, _state_payload(root, source=source))
            app = SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State"))
            registry = InFlightRegistry()
            lease = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-1",
                worker_name="Worker",
                accessible_library_ids=["movies"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=False,
                job_id="job-late",
            )
            assert lease is not None
            released = registry.unclaim("job-late", "worker-1")
            assert released is not None
            update_network_rerun_row_released(app=app, job=released, worker_id="worker-1", reason="test release")
            request = SimpleNamespace(
                job_id="job-late",
                worker_id="worker-1",
                success=True,
                output_path="",
                output_size_bytes=0,
                completion_status="processed",
                publish_state="published",
                publish_mode="handoff",
                route="network_lifecycle_single_file",
                reason_code="",
                reason="",
                error_message="",
                queue_terminal=False,
                retry_on_failure=True,
                job_kind="csv_rerun_row",
                rerun_batch_id="batch-1",
                rerun_row_key="row-1",
                planned_output_path=str(root / "Handoff" / "batch-1" / "row-1"),
                worker_result_artifact_path="",
            )

            record_late_network_rerun_row_done(app=app, request=request)

            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(row["status"], "pending_claim")
            self.assertTrue(row["claimable"])
            self.assertEqual(row["last_late_reducer_result"]["classification"], "late_done_report")
            self.assertEqual(row["late_done_count"], 1)

    def test_worker_handoff_probe_writes_reads_lists_and_deletes_probe_only(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            planned = Path(td) / "Handoff" / "batch-1" / "row-1"
            claim = ClaimResponse(
                status="ok",
                job_id="job-1",
                source_path=str(Path(td) / "Movies" / "Movie.mkv"),
                job_kind="csv_rerun_row",
                planned_output_path=str(planned),
            )

            probe = _probe_csv_rerun_handoff(claim)

            self.assertTrue(probe["ok"])
            self.assertEqual(probe["cleanup_result"], "probe_file_deleted")
            self.assertTrue(planned.exists())
            self.assertEqual(list(planned.iterdir()), [])

    def test_csv_rerun_worker_config_rewrites_handoff_and_isolated_local_base(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            planned = root / "Handoff" / "batch-1" / "row-1"
            metadata = {
                "job_kind": "csv_rerun_row",
                "rerun_batch_id": "batch-1",
                "rerun_row_key": "row-1",
                "planned_output_path": str(planned),
                "output_handoff": {"ready": True},
            }
            resolved = ResolvedPaths(
                app_root=root,
                workspace_root=root,
                pipeline_path=root / "MediaPipeline.ps1",
                config_path=root / "config.psd1",
                audit_script_path=root / "Audit.ps1",
                rerun_script_path=root / "Rerun.ps1",
                powershell_host=None,
                local_base=root / "LocalBase",
                state_root=root / "State",
                config_data={
                    "WorkerHonorCoordinatorPolicy": False,
                    "Outsource": str(root / "OriginalOut"),
                    "LocalBase": str(root / "LocalBase"),
                    "LibraryProfiles": [{"id": "movies", "output_path": str(root / "OriginalOut")}],
                },
            )
            job = SimpleNamespace(job_id="job-1", worker_id="worker-1", claim_metadata=metadata, encode_config={})

            launch_resolved, evidence = materialize_worker_effective_config(resolved, job=job)

            self.assertEqual(evidence["status"], "applied")
            self.assertEqual(launch_resolved.config_data["Outsource"], str(planned))
            self.assertEqual(launch_resolved.config_data["LibraryProfiles"][0]["output_path"], str(planned))
            self.assertIn("NetworkCsvRerun", launch_resolved.config_data["LocalBase"])
            self.assertTrue(Path(launch_resolved.config_path).exists())


if __name__ == "__main__":
    unittest.main()
