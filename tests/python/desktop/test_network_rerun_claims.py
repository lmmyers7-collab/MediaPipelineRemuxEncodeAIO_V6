from __future__ import annotations

import json
import hashlib
import os
import subprocess
import tempfile
import threading
import time
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from mediapipeline.core.kernel.models import ResolvedPaths
from mediapipeline.desktop.network.coordinator import CoordinatorDispatcher
from mediapipeline.desktop.network.processing_policy import materialize_worker_effective_config
from mediapipeline.desktop.network.protocol import ClaimResponse, DoneRequest
from mediapipeline.desktop.network.registry import InFlightRegistry
from mediapipeline.desktop.network import rerun_claims as rerun_claims_module
from mediapipeline.core.processes import rerun_facade as rerun_facade_module
from mediapipeline.core.processes import rerun_results_support as rerun_results_support_module
from mediapipeline.desktop.network.rerun_claims import (
    claim_next_network_rerun_row,
    record_late_network_rerun_row_done,
    request_network_rerun_row_retry,
    rollback_network_rerun_claim,
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
    source_stat = source.stat()
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
        "source_size": source_stat.st_size,
        "source_mtime_utc": datetime.fromtimestamp(source_stat.st_mtime, UTC).isoformat(),
        "source_identity_v2": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_identity_v2_algorithm": "sha256",
        "source_content_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "source_content_sha256_algorithm": "sha256-full-file",
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
        worker_result_artifact=json.loads(artifact_path.read_text(encoding="utf-8")),
        worker_result_artifact_path=str(artifact_path),
    )


def _request_for_worker_failure(*, job_id: str, reason: str = "source temporarily unavailable") -> SimpleNamespace:
    return SimpleNamespace(
        job_id=job_id,
        worker_id="worker-1",
        success=False,
        output_path="",
        output_size_bytes=0,
        completion_status="failed",
        publish_state="",
        publish_mode="",
        route="network_lifecycle_single_file",
        reason_code="SOURCE_UNAVAILABLE",
        reason=reason,
        error_message="",
        queue_terminal=False,
        retry_on_failure=True,
        worker_result_artifact_path="",
    )


def _late_done_request(root: Path, *, batch_id: str = "batch-1", row_key: str = "row-1") -> SimpleNamespace:
    return SimpleNamespace(
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
        rerun_batch_id=batch_id,
        rerun_row_key=row_key,
        planned_output_path=str(root / "Handoff" / "batch-1" / "row-1"),
        worker_result_artifact_path="",
    )


def _accepted_late_report(source: Path) -> dict[str, object]:
    return {
        "accepted": True,
        "authorization_status": "accepted",
        "job_id": "job-late",
        "worker_id": "worker-1",
        "reclaimed_worker_id": "worker-1",
        "source_path": str(source),
        "job_kind": "csv_rerun_row",
        "rerun_batch_id": "batch-1",
        "rerun_row_key": "row-1",
    }


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
    def test_late_rerun_state_path_rejects_nonopaque_and_mismatched_paths(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app = SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State"))
            state_root = root / "State" / "Rerun" / "Network"
            canonical = state_root / "batch-1.json"

            for batch_id in (
                "../outside",
                "..\\outside",
                "/absolute",
                "C:\\absolute",
                "batch/child",
                "batch\\child",
                "batch.json",
            ):
                with self.subTest(batch_id=batch_id):
                    self.assertIsNone(
                        rerun_claims_module._metadata_state_path(  # noqa: SLF001
                            {"rerun_batch_id": batch_id},
                            app,
                        )
                    )

            self.assertEqual(
                rerun_claims_module._metadata_state_path(  # noqa: SLF001
                    {"rerun_batch_id": "batch-1", "batch_state_path": str(canonical)},
                    app,
                ),
                canonical.resolve(),
            )
            self.assertIsNone(
                rerun_claims_module._metadata_state_path(  # noqa: SLF001
                    {"rerun_batch_id": "batch-1", "batch_state_path": str(root / "outside.json")},
                    app,
                )
            )

    def test_late_rerun_rejects_persisted_batch_identity_mismatch_without_write(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            payload = _state_payload(root, source=source)
            payload["batch_id"] = "batch-other"
            state_path = _write_batch(root, payload)
            before = state_path.read_bytes()
            app = SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State"))

            recorded = record_late_network_rerun_row_done(
                app=app,
                request=_late_done_request(root),
                late_report=_accepted_late_report(source),
            )

            self.assertFalse(recorded)
            self.assertEqual(state_path.read_bytes(), before)

    def test_late_rerun_binds_row_to_registry_reclaim_identity(self) -> None:
        mismatches = {
            "job_id": {"job_id": "job-other"},
            "worker_id": {"worker_id": "worker-other"},
            "source_path": {"source_path": "C:/Media/Other.mkv"},
        }
        for label, changes in mismatches.items():
            with self.subTest(label=label), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                source = root / "Movies" / "Movie.mkv"
                source.parent.mkdir(parents=True)
                source.write_bytes(b"source")
                state_path = _write_batch(root, _state_payload(root, source=source))
                before = state_path.read_bytes()
                app = SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State"))
                report = {**_accepted_late_report(source), **changes}

                recorded = record_late_network_rerun_row_done(
                    app=app,
                    request=_late_done_request(root),
                    late_report=report,
                )

                self.assertFalse(recorded)
                self.assertEqual(state_path.read_bytes(), before)

    def test_mixed_terminal_batch_prefers_review_over_retry_exhausted_failure_and_skip(self) -> None:
        payload = {
            "rows": [
                {"status": "review_required", "terminal": True},
                {"status": "retry_exhausted", "terminal": True},
                {"status": "destination_policy_failed", "terminal": True},
                {"status": "skipped", "terminal": True},
            ]
        }

        rerun_claims_module._update_counts(payload)

        self.assertEqual(payload["status"], "review_required")
        self.assertEqual(payload["terminal_row_count"], 4)
        self.assertEqual(payload["review_row_count"], 1)
        self.assertEqual(payload["retry_exhausted_row_count"], 1)
        self.assertEqual(payload["failed_row_count"], 2)
        self.assertEqual(payload["skipped_row_count"], 1)
        self.assertTrue(payload["batch_terminal"])

    def test_skipped_rows_are_terminal_and_batch_completes_with_skips(self) -> None:
        rows = rerun_facade_module._network_rerun_batch_rows(
            {
                "rows": [
                    {
                        "row_key": "skipped",
                        "row_index": 1,
                        "source_path": "",
                        "claimable": False,
                        "start_ready": False,
                        "skipped": True,
                        "local_preview_status": "filtered",
                    },
                    {
                        "row_key": "complete",
                        "row_index": 2,
                        "source_path": "Movie.mkv",
                        "claimable": False,
                        "start_ready": False,
                        "skipped": False,
                        "local_preview_status": "warning",
                    },
                ]
            }
        )
        self.assertEqual(rows[0]["status"], "skipped")
        self.assertTrue(rows[0]["terminal"])
        self.assertEqual(rows[1]["status"], "review_required")
        self.assertTrue(rows[1]["terminal"])

        payload = {
            "rows": [
                {"status": "complete", "terminal": True, "claimable": False},
                {"status": "skipped", "terminal": True, "claimable": False},
            ]
        }
        rerun_claims_module._update_counts(payload)
        self.assertEqual(payload["status"], "completed_with_skips")
        self.assertEqual(payload["skipped_row_count"], 1)
        self.assertEqual(payload["terminal_row_count"], 2)
        self.assertEqual(payload["active_row_count"], 0)
        self.assertTrue(payload["batch_terminal"])

    def test_durable_worker_failed_terminal_maps_to_terminal_queue_failure(self) -> None:
        status = rerun_results_support_module._queue_status_for_row(
            {"status": "worker_failed_pending_reduction"},
            manifest_status="active",
        )
        self.assertEqual(status["status_key"], "failed")
        self.assertTrue(status["terminal"])

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
                worker_result_artifact=json.loads(artifact_path.read_text(encoding="utf-8")),
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

    def test_http_claim_delivery_rollback_retains_registry_when_batch_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir()
            source.write_bytes(b"source")
            state_path = _write_batch(root, _state_payload(root, source=source))
            inflight_path = root / "State" / "coordinator_inflight.json"
            app = SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State"), queue_records=[])
            registry = InFlightRegistry()
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._app = app
            dispatcher._registry = registry
            dispatcher._claim_lock = threading.Lock()
            dispatcher._accepting_claims = True
            dispatcher._inflight_state_path = lambda: inflight_path  # type: ignore[method-assign]
            dispatcher._compute_retry_after_seconds = lambda: 5  # type: ignore[method-assign]
            dispatcher._coordinator_max_job_retries = lambda: 3  # type: ignore[method-assign]
            dispatcher._source_has_prior_failure = lambda _source_path: False  # type: ignore[method-assign]
            dispatcher._snapshot_encode_config = lambda _worker_name, record=None: {}  # type: ignore[method-assign]
            dispatcher._scan_for_next_record = lambda *_args, **_kwargs: (None, {})  # type: ignore[method-assign]
            dispatcher._safe_log_cluster_event = lambda *_args, **_kwargs: None  # type: ignore[method-assign]

            original_write_state = rerun_claims_module._write_state
            write_count = 0

            def fail_rollback_write(path: Path, payload: dict[str, object]) -> None:
                nonlocal write_count
                write_count += 1
                if write_count == 2:
                    raise OSError("injected response-delivery rollback write failure")
                original_write_state(path, payload)

            handler = SimpleNamespace(
                _send_json=mock.Mock(side_effect=RuntimeError("socket closed during claim delivery"))
            )
            with mock.patch.object(rerun_claims_module, "_write_state", side_effect=fail_rollback_write):
                with self.assertRaisesRegex(RuntimeError, "socket closed during claim delivery"):
                    CoordinatorDispatcher._http_claim(
                        dispatcher,
                        handler,
                        {"worker_id": "worker-1", "worker_name": "Worker", "accessible_library_ids": "movies"},
                    )

            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            job_id = str(row["active_claim"]["job_id"])
            self.assertEqual(row["status"], "claimed")
            self.assertTrue(registry.is_active(job_id, "worker-1"))
            restored = InFlightRegistry()
            self.assertTrue(restored.load(inflight_path))
            self.assertTrue(restored.is_active(job_id, "worker-1"))

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

    def test_rerun_claim_rollback_retains_registry_owner_when_batch_rollback_fails(self) -> None:
        for failure_target in ("read", "write"):
            with self.subTest(failure_target=failure_target), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                source = root / "Movies" / "Movie.mkv"
                source.parent.mkdir()
                source.write_bytes(b"source")
                state_path = _write_batch(root, _state_payload(root, source=source))
                inflight_path = root / "State" / "coordinator_inflight.json"
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
                    job_id="job-rollback",
                )
                assert lease is not None
                registry.save(inflight_path)
                patch_target = "_read_state" if failure_target == "read" else "_write_state"

                with mock.patch.object(
                    rerun_claims_module,
                    patch_target,
                    side_effect=OSError(f"injected batch {failure_target} failure"),
                ):
                    with self.assertRaisesRegex(OSError, f"injected batch {failure_target} failure"):
                        rollback_network_rerun_claim(lease, registry, reason="delivery failed")

                self.assertTrue(registry.is_active("job-rollback", "worker-1"))
                persisted_row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
                self.assertEqual(persisted_row["status"], "claimed")
                self.assertEqual(persisted_row["active_claim"]["job_id"], "job-rollback")
                restored = InFlightRegistry()
                self.assertTrue(restored.load(inflight_path))
                self.assertTrue(restored.is_active("job-rollback", "worker-1"))

                rollback_network_rerun_claim(lease, registry, reason="retry delivery rollback")
                self.assertFalse(registry.is_active("job-rollback", "worker-1"))
                rolled_back_row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
                self.assertEqual(rolled_back_row["status"], "pending_claim")
                self.assertTrue(rolled_back_row["claimable"])

    def test_rerun_claim_rollback_keeps_registry_quarantine_when_release_is_rejected(self) -> None:
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
                job_id="job-registry-reject",
            )
            assert lease is not None

            with mock.patch.object(registry, "rollback_claim", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "Registry retained network rerun claim"):
                    rollback_network_rerun_claim(lease, registry, reason="delivery failed")

            self.assertTrue(registry.is_active("job-registry-reject", "worker-1"))
            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(row["status"], "pending_claim")
            self.assertTrue(row["claimable"])

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
                worker_result_artifact=json.loads(artifact_path.read_text(encoding="utf-8")),
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
            self.assertTrue(row["terminal"])
            self.assertEqual(
                [event["state"] for event in row["timeline"]][-2:],
                ["destination_policy_applying", "pending_publish"],
            )
            self.assertTrue(row["operator_action_required"])
            self.assertTrue(row["what"])
            self.assertTrue(row["next_action"])
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
            self.assertTrue(row["terminal"])
            self.assertTrue(row["manual_recovery_required"])
            self.assertTrue(row["operator_action_required"])
            self.assertEqual(row["timeline"][-1]["state"], "destination_policy_failed")
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
                worker_result_artifact=json.loads(artifact_path.read_text(encoding="utf-8")),
                worker_result_artifact_path=str(artifact_path),
            )

            update_network_rerun_row_done(app=app, job=completed, request=request)

            state = json.loads(state_path.read_text(encoding="utf-8"))
            row = state["rows"][0]
            self.assertEqual(row["status"], "review_required")
            self.assertEqual(row["reducer_result"]["classification"], "output_missing")
            self.assertFalse(row["reducer_result"]["retryable"])
            self.assertTrue(row["manual_recovery_required"])
            self.assertEqual(row["reason_code"], "network_output_missing_after_success")
            self.assertEqual(state["status"], "review_required")
            self.assertTrue(state["terminal_at_utc"])

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
                worker_result_artifact=json.loads(artifact_path.read_text(encoding="utf-8")),
                worker_result_artifact_path=str(artifact_path),
            )

            update_network_rerun_row_done(app=app, job=completed, request=request)

            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(row["status"], "review_required")
            self.assertEqual(row["reducer_result"]["classification"], "corrupt_result")
            self.assertIn("artifact_row_key_mismatch", row["reducer_result"]["mismatches"])
            self.assertFalse(row["reducer_result"]["retryable"])
            self.assertEqual(row["reason_code"], "network_worker_artifact_mismatch")
            self.assertTrue(row["operator_action_required"])

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
            foreign_request = SimpleNamespace(**{**vars(request), "worker_id": "worker-foreign"})
            self.assertFalse(
                update_network_rerun_row_done(
                    app=app,
                    job=completed,
                    request=foreign_request,
                )
            )

            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(row["status"], "retry_scheduled")
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
            request = _late_done_request(root)

            record_late_network_rerun_row_done(
                app=app,
                request=request,
                late_report=_accepted_late_report(source),
            )

            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(row["status"], "pending_claim")
            self.assertTrue(row["claimable"])
            self.assertEqual(row["last_late_reducer_result"]["classification"], "late_done_report")
            self.assertEqual(row["late_done_count"], 1)

    def test_retryable_worker_failure_schedules_durable_claimable_backoff(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app, state_path, completed, _source, _output_path = _claim_row_for_reducer(root, job_id="job-retry")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["rows"][0].update(
                {
                    "attempt_count": 1,
                    "retry_count": 0,
                    "retry_limit": 3,
                }
            )
            state_path.write_text(json.dumps(state), encoding="utf-8")

            update_network_rerun_row_done(
                app=app,
                job=completed,
                request=_request_for_worker_failure(job_id="job-retry"),
            )

            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(row["status"], "retry_scheduled")
            self.assertEqual(row["claim_status"], "retry_scheduled")
            self.assertTrue(row["claimable"])
            self.assertEqual(row["attempt_count"], 1)
            self.assertEqual(row["retry_count"], 1)
            self.assertEqual(row["retry_limit"], 3)
            self.assertGreater(row["retry_after_seconds"], 0)
            reduced_at = datetime.fromisoformat(row["reducer_result"]["reduced_at_utc"])
            next_retry_at = datetime.fromisoformat(row["next_retry_at_utc"])
            self.assertGreater(next_retry_at, reduced_at)

    def test_retry_exhaustion_is_terminal_but_explicitly_manual_recoverable(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app, state_path, completed, _source, _output_path = _claim_row_for_reducer(root, job_id="job-exhausted")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["rows"][0].update(
                {
                    "attempt_count": 3,
                    "retry_count": 2,
                    "retry_limit": 3,
                }
            )
            state_path.write_text(json.dumps(state), encoding="utf-8")

            update_network_rerun_row_done(
                app=app,
                job=completed,
                request=_request_for_worker_failure(job_id="job-exhausted", reason="source remained unavailable"),
            )

            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(row["status"], "retry_exhausted")
            self.assertFalse(row["claimable"])
            self.assertEqual(row["retry_count"], 3)
            self.assertEqual(row["retry_limit"], 3)
            self.assertTrue(row["terminal"])
            self.assertTrue(row["manual_recovery_required"])
            self.assertTrue(row["manual_recovery_available"])
            self.assertEqual(row["reason_code"], "SOURCE_UNAVAILABLE")
            self.assertTrue(row["first_failure"]["at_utc"])
            self.assertEqual(row["last_failure"]["reason_code"], "SOURCE_UNAVAILABLE")
            self.assertEqual(row["last_error"], "source remained unavailable")
            self.assertTrue(row["next_action"])
            self.assertTrue(row["operator_action"])
            state = json.loads(state_path.read_text(encoding="utf-8"))
            self.assertEqual(state["status"], "retry_exhausted")
            self.assertEqual(state["terminal_row_count"], 1)
            self.assertTrue(state["terminal_at_utc"])

    def test_concurrent_two_row_done_updates_preserve_both_rows(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_a = root / "Movies" / "A.mkv"
            source_b = root / "Movies" / "B.mkv"
            source_a.parent.mkdir(parents=True)
            source_a.write_bytes(b"source-a")
            source_b.write_bytes(b"source-b")
            payload = _state_payload(root, source=source_a)
            row_a = payload["rows"][0]
            row_b = json.loads(json.dumps(row_a))
            for row, row_key, source, job_id, worker_id in (
                (row_a, "row-a", source_a, "job-a", "worker-a"),
                (row_b, "row-b", source_b, "job-b", "worker-b"),
            ):
                row.update(
                    {
                        "row_key": row_key,
                        "source_path": str(source),
                        "planned_output_path": str(root / "Handoff" / "batch-1" / row_key),
                        "status": "claimed",
                        "claim_status": "claimed",
                        "claimable": False,
                        "attempt_count": 1,
                        "retry_count": 0,
                        "retry_limit": 3,
                        "active_claim": {"job_id": job_id, "worker_id": worker_id},
                        "source_size": source.stat().st_size,
                        "source_mtime_utc": datetime.fromtimestamp(
                            source.stat().st_mtime,
                            UTC,
                        ).isoformat(),
                        "source_identity_v2": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "source_content_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                    }
                )
            payload["rows"] = [row_a, row_b]
            state_path = _write_batch(root, payload)
            app = SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State"))

            def job(row_key: str, job_id: str, worker_id: str) -> SimpleNamespace:
                return SimpleNamespace(
                    job_id=job_id,
                    claim_metadata={
                        "job_kind": "csv_rerun_row",
                        "job_id": job_id,
                        "rerun_batch_id": "batch-1",
                        "rerun_row_key": row_key,
                        "planned_output_path": str(root / "Handoff" / "batch-1" / row_key),
                        "batch_state_path": str(state_path),
                        "worker_id": worker_id,
                    },
                )

            first_read = threading.Event()
            second_read = threading.Event()
            read_count = 0
            read_count_lock = threading.Lock()
            original_read = rerun_claims_module._read_state

            def coordinated_read(path: Path) -> dict[str, object]:
                nonlocal read_count
                result = original_read(path)
                with read_count_lock:
                    read_count += 1
                    current = read_count
                if current == 1:
                    first_read.set()
                    second_read.wait(0.25)
                elif current == 2:
                    second_read.set()
                return result

            errors: list[BaseException] = []

            def finish(row_key: str, job_id: str, worker_id: str) -> None:
                try:
                    request = _request_for_worker_failure(job_id=job_id)
                    request.worker_id = worker_id
                    source = source_a if row_key == "row-a" else source_b
                    request.source_identity = {
                        "source_identity_v2": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "source_content_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
                        "source_content_sha256_algorithm": "sha256-full-file",
                        "source_size": source.stat().st_size,
                        "source_mtime_utc": datetime.fromtimestamp(
                            source.stat().st_mtime,
                            UTC,
                        ).isoformat(),
                    }
                    updated = update_network_rerun_row_done(
                        app=app,
                        job=job(row_key, job_id, worker_id),
                        request=request,
                    )
                    self.assertTrue(updated)
                except BaseException as exc:  # pragma: no cover - surfaced below
                    errors.append(exc)

            with mock.patch.object(rerun_claims_module, "_read_state", side_effect=coordinated_read):
                threads = [
                    threading.Thread(target=finish, args=("row-a", "job-a", "worker-a")),
                    threading.Thread(target=finish, args=("row-b", "job-b", "worker-b")),
                ]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join(timeout=2)

            self.assertFalse(errors, errors)
            self.assertFalse(any(thread.is_alive() for thread in threads))
            rows = {
                row["row_key"]: row
                for row in json.loads(state_path.read_text(encoding="utf-8"))["rows"]
            }
            self.assertEqual(rows["row-a"]["status"], "retry_scheduled")
            self.assertEqual(rows["row-b"]["status"], "retry_scheduled")
            self.assertEqual(rows["row-a"]["reducer_result"]["job_id"], "job-a")
            self.assertEqual(rows["row-b"]["reducer_result"]["job_id"], "job-b")

    def test_retry_revalidates_same_path_size_mtime_and_identity_v2(self) -> None:
        cases = ("size", "mtime", "identity_v2")
        for mismatch_kind in cases:
            with self.subTest(mismatch=mismatch_kind), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                source = root / "Movies" / "Movie.mkv"
                source.parent.mkdir(parents=True)
                source.write_bytes(b"source")
                payload = _state_payload(root, source=source)
                row = payload["rows"][0]
                row.update(
                    {
                        "status": "retry_scheduled",
                        "claim_status": "retry_scheduled",
                        "claimable": True,
                        "retry_count": 1,
                        "retry_limit": 3,
                        "next_retry_at_utc": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
                    }
                )
                if mismatch_kind == "size":
                    source.write_bytes(b"same-path-but-changed")
                elif mismatch_kind == "mtime":
                    row["source_mtime_utc"] = "2000-01-01T00:00:00+00:00"
                else:
                    planned_mtime_ns = source.stat().st_mtime_ns
                    source.write_bytes(b"SOURCE")
                    os.utime(source, ns=(planned_mtime_ns, planned_mtime_ns))
                state_path = _write_batch(root, payload)
                app = SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State"))

                lease = claim_next_network_rerun_row(
                    app=app,
                    registry=InFlightRegistry(),
                    worker_id="worker-1",
                    worker_name="Worker",
                    accessible_library_ids=["movies"],
                    encode_config_for_row=lambda _record: {},
                    allow_local_handoff=False,
                    job_id=f"job-{mismatch_kind}",
                )

                self.assertIsNone(lease)
                state = json.loads(state_path.read_text(encoding="utf-8"))
                blocked = state["rows"][0]
                self.assertEqual(blocked["status"], "review_required")
                self.assertFalse(blocked["claimable"])
                self.assertTrue(blocked["manual_recovery_required"])
                self.assertEqual(blocked["reason_code"], "network_source_identity_changed")
                self.assertIn(f"source_{mismatch_kind}_mismatch", blocked["source_replay_evidence"]["mismatches"])
                self.assertEqual(state["status"], "review_required")

    def test_retry_revalidates_full_content_when_size_mtime_and_sample_identity_match(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes((b"a" * (1024 * 1024)) + b"middle-before" + (b"z" * (1024 * 1024)))
            payload = _state_payload(root, source=source)
            row = payload["rows"][0]
            row.update(
                {
                    "status": "retry_scheduled",
                    "claim_status": "retry_scheduled",
                    "retry_count": 1,
                    "retry_limit": 3,
                    "next_retry_at_utc": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
                    "source_identity_v2": "sample-identity-remains-the-same",
                    "source_identity_v2_algorithm": "size-duration-codec-sample-v1",
                }
            )
            planned_mtime_ns = source.stat().st_mtime_ns
            content = bytearray(source.read_bytes())
            middle = len(content) // 2
            content[middle : middle + len(b"middle-before")] = b"middle-after!"
            source.write_bytes(content)
            os.utime(source, ns=(planned_mtime_ns, planned_mtime_ns))
            state_path = _write_batch(root, payload)

            with mock.patch.object(
                rerun_claims_module,
                "_source_identity_v2",
                return_value=("sample-identity-remains-the-same", ""),
            ):
                lease = claim_next_network_rerun_row(
                    app=SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State")),
                    registry=InFlightRegistry(),
                    worker_id="worker-1",
                    worker_name="Worker",
                    accessible_library_ids=["movies"],
                    encode_config_for_row=lambda _record: {},
                    allow_local_handoff=False,
                    job_id="job-middle-mutation",
                )

            self.assertIsNone(lease)
            blocked = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(blocked["status"], "review_required")
            self.assertIn(
                "source_content_sha256_mismatch",
                blocked["source_replay_evidence"]["mismatches"],
            )

    def test_recovery_without_planned_full_content_hash_fails_closed_without_baselining(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            payload = _state_payload(root, source=source)
            row = payload["rows"][0]
            row.pop("source_content_sha256", None)
            row.pop("source_content_sha256_algorithm", None)
            row.update(
                {
                    "status": "retry_scheduled",
                    "claim_status": "retry_scheduled",
                    "retry_count": 1,
                    "retry_limit": 3,
                    "next_retry_at_utc": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
                }
            )
            state_path = _write_batch(root, payload)

            lease = claim_next_network_rerun_row(
                app=SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State")),
                registry=InFlightRegistry(),
                worker_id="worker-1",
                worker_name="Worker",
                accessible_library_ids=["movies"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=False,
                job_id="job-no-strong-baseline",
            )

            self.assertIsNone(lease)
            blocked = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(blocked["status"], "review_required")
            self.assertIn(
                "source_content_sha256_missing",
                blocked["source_replay_evidence"]["mismatches"],
            )
            self.assertNotIn("source_content_sha256", blocked)

    def test_recovery_rejects_noncanonical_or_malformed_full_content_hash_baselines(self) -> None:
        cases = (
            (hashlib.sha256(b"source").hexdigest(), "", "source_content_sha256_algorithm_invalid"),
            (hashlib.sha256(b"source").hexdigest(), "full-sha256", "source_content_sha256_algorithm_invalid"),
            ("g" * 64, "sha256-full-file", "source_content_sha256_invalid"),
            ("a" * 63, "sha256-full-file", "source_content_sha256_invalid"),
        )
        for digest, algorithm, mismatch in cases:
            with self.subTest(algorithm=algorithm, digest=digest), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                source = root / "Movies" / "Movie.mkv"
                source.parent.mkdir(parents=True)
                source.write_bytes(b"source")
                payload = _state_payload(root, source=source)
                row = payload["rows"][0]
                row.update(
                    {
                        "status": "retry_scheduled",
                        "claim_status": "retry_scheduled",
                        "retry_count": 1,
                        "retry_limit": 3,
                        "next_retry_at_utc": (datetime.now(UTC) - timedelta(seconds=1)).isoformat(),
                        "source_content_sha256": digest,
                        "source_content_sha256_algorithm": algorithm,
                    }
                )
                state_path = _write_batch(root, payload)

                lease = claim_next_network_rerun_row(
                    app=SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State")),
                    registry=InFlightRegistry(),
                    worker_id="worker-1",
                    worker_name="Worker",
                    accessible_library_ids=["movies"],
                    encode_config_for_row=lambda _record: {},
                    allow_local_handoff=False,
                    job_id="job-invalid-strong-baseline",
                )

                self.assertIsNone(lease)
                blocked = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
                self.assertEqual(blocked["status"], "review_required")
                self.assertIn(mismatch, blocked["source_replay_evidence"]["mismatches"])
                self.assertEqual(
                    blocked["source_replay_evidence"]["source_content_sha256_algorithm"],
                    algorithm,
                )

    def test_reducer_rejects_noncanonical_or_malformed_expected_and_request_hash_evidence(self) -> None:
        valid_digest = hashlib.sha256(b"source").hexdigest()
        valid_identity = {
            "source_content_sha256": valid_digest,
            "source_content_sha256_algorithm": "sha256-full-file",
        }
        cases = (
            (
                {**valid_identity, "source_content_sha256_algorithm": "full-sha256"},
                valid_identity,
                "source_content_sha256_algorithm_invalid",
            ),
            (
                {**valid_identity, "source_content_sha256": "g" * 64},
                valid_identity,
                "source_content_sha256_invalid",
            ),
            (
                valid_identity,
                {**valid_identity, "source_content_sha256_algorithm": "full-sha256"},
                "request_source_content_sha256_algorithm_invalid",
            ),
            (
                valid_identity,
                {**valid_identity, "source_content_sha256": "a" * 63},
                "request_source_content_sha256_invalid",
            ),
        )
        for expected, request_identity, mismatch in cases:
            with self.subTest(mismatch=mismatch):
                evidence, mismatches = rerun_claims_module._source_identity_evidence(
                    row=expected,
                    metadata={"source_identity": expected},
                    request=SimpleNamespace(source_identity=request_identity),
                )

                self.assertIn(mismatch, mismatches)
                self.assertFalse(evidence["matches"])
                self.assertEqual(
                    evidence["expected_source_content_sha256_algorithm"],
                    expected["source_content_sha256_algorithm"],
                )
                self.assertEqual(
                    evidence["request_source_content_sha256_algorithm"],
                    request_identity["source_content_sha256_algorithm"],
                )

    def test_claim_fails_closed_when_source_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            payload = _state_payload(root, source=source)
            source.unlink()
            state_path = _write_batch(root, payload)

            lease = claim_next_network_rerun_row(
                app=SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State")),
                registry=InFlightRegistry(),
                worker_id="worker-1",
                worker_name="Worker",
                accessible_library_ids=["movies"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=False,
                job_id="job-missing-source",
            )

            self.assertIsNone(lease)
            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(row["status"], "review_required")
            self.assertFalse(row["source_replay_evidence"]["matches"])
            self.assertIn("source_missing", row["source_replay_evidence"]["mismatches"])

    def test_claim_source_probe_timeout_is_bounded_and_schedules_retry(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            state_path = _write_batch(root, _state_payload(root, source=source))
            real_run = subprocess.run

            def timed_out_probe(args: object, *run_args: object, **run_kwargs: object):
                command = [str(item) for item in args] if isinstance(args, list) else []
                if (
                    "mediapipeline.core.processes.source_probe" in command
                    and "--operation" in command
                    and command[command.index("--operation") + 1] == "stat"
                    and command[command.index("--path") + 1] == str(source)
                ):
                    raise subprocess.TimeoutExpired(command, 0.05)
                return real_run(args, *run_args, **run_kwargs)

            started = time.monotonic()
            with (
                mock.patch.object(
                    rerun_claims_module,
                    "NETWORK_RERUN_SOURCE_PROBE_TIMEOUT_SECONDS",
                    0.05,
                    create=True,
                ),
                mock.patch.object(subprocess, "run", timed_out_probe),
            ):
                lease = claim_next_network_rerun_row(
                    app=SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State")),
                    registry=InFlightRegistry(),
                    worker_id="worker-1",
                    worker_name="Worker",
                    accessible_library_ids=["movies"],
                    encode_config_for_row=lambda _record: {},
                    allow_local_handoff=False,
                    job_id="job-offline-source",
                )
            elapsed = time.monotonic() - started

            self.assertIsNone(lease)
            self.assertLess(elapsed, 0.2)
            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(row["status"], "retry_scheduled")
            self.assertTrue(row["claimable"])
            self.assertEqual(row["reason_code"], "source_access_failed")
            self.assertIn("source_access_failed", row["source_replay_evidence"]["mismatches"])

    def test_offline_source_root_retries_then_reconnects_with_same_identity(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            state_path = _write_batch(root, _state_payload(root, source=source))
            app = SimpleNamespace(resolved=_resolved_paths(root))
            real_probe = rerun_claims_module._bounded_path_stat

            def offline_root_stat(path: Path):
                if path == source.parent:
                    raise OSError("test share offline")
                return real_probe(path)

            with mock.patch.object(rerun_claims_module, "_bounded_path_stat", offline_root_stat):
                first = claim_next_network_rerun_row(
                    app=app,
                    registry=InFlightRegistry(),
                    worker_id="worker-1",
                    worker_name="Worker",
                    accessible_library_ids=["movies"],
                    encode_config_for_row=lambda _record: {},
                    allow_local_handoff=False,
                    job_id="job-offline-first",
                )
            self.assertIsNone(first)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            waiting = state["rows"][0]
            self.assertEqual(waiting["status"], "retry_scheduled")
            self.assertEqual(waiting["reason_code"], "source_access_failed")
            waiting["next_retry_at_utc"] = (datetime.now(UTC) - timedelta(seconds=1)).isoformat()
            state_path.write_text(json.dumps(state), encoding="utf-8")

            lease = claim_next_network_rerun_row(
                app=app,
                registry=InFlightRegistry(),
                worker_id="worker-1",
                worker_name="Worker",
                accessible_library_ids=["movies"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=False,
                job_id="job-after-reconnect",
            )

            self.assertIsNotNone(lease)
            self.assertEqual(lease.response.job_id, "job-after-reconnect")
            claimed = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(claimed["status"], "claimed")
            self.assertEqual(claimed["retry_count"], 1)
            self.assertTrue(claimed["source_replay_evidence"]["matches"])

    def test_identity_read_timeout_uses_bounded_retry_not_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            state_path = _write_batch(root, _state_payload(root, source=source))
            real_probe = rerun_claims_module.run_source_probe

            def identity_timeout(operation: str, path: Path, **kwargs: object):
                if operation == "sha256" and path == source:
                    raise TimeoutError("sample read timed out")
                return real_probe(operation, path, **kwargs)

            with mock.patch.object(rerun_claims_module, "run_source_probe", identity_timeout):
                lease = claim_next_network_rerun_row(
                    app=SimpleNamespace(resolved=_resolved_paths(root)),
                    registry=InFlightRegistry(),
                    worker_id="worker-1",
                    worker_name="Worker",
                    accessible_library_ids=["movies"],
                    encode_config_for_row=lambda _record: {},
                    allow_local_handoff=False,
                    job_id="job-identity-timeout",
                )

            self.assertIsNone(lease)
            waiting = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(waiting["status"], "retry_scheduled")
            self.assertEqual(waiting["reason_code"], "source_access_failed")
            self.assertIn("source_identity_probe_timeout", waiting["source_replay_evidence"]["mismatches"])

    def test_ffprobe_nonzero_uses_bounded_access_retry_not_review(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            payload = _state_payload(root, source=source)
            payload["rows"][0]["source_identity_v2"] = "sample-identity"
            payload["rows"][0]["source_identity_v2_algorithm"] = "size-duration-codec-sample-v1"
            state_path = _write_batch(root, payload)

            with mock.patch.object(
                rerun_claims_module,
                "_source_identity_v2",
                return_value=("", "source_identity_ffprobe_failed"),
            ):
                lease = claim_next_network_rerun_row(
                    app=SimpleNamespace(resolved=_resolved_paths(root)),
                    registry=InFlightRegistry(),
                    worker_id="worker-1",
                    worker_name="Worker",
                    accessible_library_ids=["movies"],
                    encode_config_for_row=lambda _record: {},
                    allow_local_handoff=False,
                    job_id="job-ffprobe-nonzero",
                )

            self.assertIsNone(lease)
            waiting = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(waiting["status"], "retry_scheduled")
            self.assertEqual(waiting["reason_code"], "source_access_failed")
            self.assertIn("source_identity_ffprobe_failed", waiting["source_replay_evidence"]["mismatches"])
            self.assertIn("source_access_failed", waiting["source_replay_evidence"]["mismatches"])

    def test_offline_source_root_exhausts_bounded_retries(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            payload = _state_payload(root, source=source)
            payload["rows"][0]["retry_limit"] = 2
            state_path = _write_batch(root, payload)
            app = SimpleNamespace(resolved=_resolved_paths(root))
            real_probe = rerun_claims_module._bounded_path_stat

            def offline_root_stat(path: Path):
                if path == source.parent:
                    raise OSError("test share offline")
                return real_probe(path)

            for attempt in range(2):
                with mock.patch.object(rerun_claims_module, "_bounded_path_stat", offline_root_stat):
                    lease = claim_next_network_rerun_row(
                        app=app,
                        registry=InFlightRegistry(),
                        worker_id="worker-1",
                        worker_name="Worker",
                        accessible_library_ids=["movies"],
                        encode_config_for_row=lambda _record: {},
                        allow_local_handoff=False,
                        job_id=f"job-offline-{attempt}",
                    )
                self.assertIsNone(lease)
                state = json.loads(state_path.read_text(encoding="utf-8"))
                if attempt == 0:
                    state["rows"][0]["next_retry_at_utc"] = (
                        datetime.now(UTC) - timedelta(seconds=1)
                    ).isoformat()
                    state_path.write_text(json.dumps(state), encoding="utf-8")

            state = json.loads(state_path.read_text(encoding="utf-8"))
            exhausted = state["rows"][0]
            self.assertEqual(exhausted["status"], "retry_exhausted")
            self.assertEqual(exhausted["retry_count"], 2)
            self.assertTrue(exhausted["manual_recovery_available"])
            self.assertEqual(state["status"], "retry_exhausted")

    def test_missing_configured_global_subroot_is_temporary_location_outage(self) -> None:
        for configured_via in ("resolved", "config"):
            with self.subTest(configured_via=configured_via), tempfile.TemporaryDirectory() as td:
                root = Path(td)
                configured_root = root / "MountedMovies"
                source = configured_root / "Movie.mkv"
                source.parent.mkdir(parents=True)
                source.write_bytes(b"source")
                state_path = _write_batch(root, _state_payload(root, source=source))
                resolved = _resolved_paths(root)
                resolved.config_data["LibraryProfiles"] = [
                    {"id": "movies", "source_path": str(root), "output_path": str(root / "Outsource")}
                ]
                if configured_via == "resolved":
                    resolved.source_movies = configured_root
                else:
                    resolved.config_data["SourceMovies"] = str(configured_root)
                source.unlink()
                configured_root.rmdir()

                lease = claim_next_network_rerun_row(
                    app=SimpleNamespace(resolved=resolved),
                    registry=InFlightRegistry(),
                    worker_id="worker-1",
                    worker_name="Worker",
                    accessible_library_ids=["movies"],
                    encode_config_for_row=lambda _record: {},
                    allow_local_handoff=False,
                    job_id=f"job-missing-subroot-{configured_via}",
                )

                self.assertIsNone(lease)
                waiting = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
                self.assertEqual(waiting["status"], "retry_scheduled")
                self.assertEqual(waiting["reason_code"], "source_location_unavailable")
                self.assertEqual(
                    os.path.normcase(waiting["source_replay_evidence"]["source_root"]),
                    os.path.normcase(str(configured_root)),
                )

    def test_blank_library_id_does_not_borrow_an_unrelated_profile_root(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "External" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            payload = _state_payload(root, source=source)
            row = payload["rows"][0]
            row["library_id"] = ""
            row["source_mapping"] = {
                "method": "coordinator_source_path",
                "library_id": "",
                "relative_path": "",
            }
            state_path = _write_batch(root, payload)
            resolved = _resolved_paths(root)
            resolved.config_data["LibraryProfiles"] = [
                {"id": "movies", "source_path": str(root / "OfflineMovies")},
                {"id": "tv", "source_path": str(root / "OfflineTv")},
            ]

            lease = claim_next_network_rerun_row(
                app=SimpleNamespace(resolved=resolved),
                registry=InFlightRegistry(),
                worker_id="worker-1",
                worker_name="Worker",
                accessible_library_ids=None,
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=False,
                job_id="job-unmapped-source",
            )

            self.assertIsNotNone(lease)
            claimed = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertTrue(claimed["source_replay_evidence"]["root_reachable"])
            self.assertNotIn("OfflineMovies", claimed["source_replay_evidence"]["source_root"])

    def test_manual_retry_reopens_exact_exhausted_row_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            payload = _state_payload(root, source=source)
            row = payload["rows"][0]
            row.update(
                {
                    "status": "retry_exhausted",
                    "claim_status": "retry_exhausted",
                    "claimable": False,
                    "terminal": True,
                    "retry_count": 3,
                    "retry_limit": 3,
                    "manual_recovery_required": True,
                    "manual_recovery_available": True,
                    "first_failure": {"reason_code": "source_access_failed"},
                    "last_failure": {"reason_code": "source_access_failed"},
                }
            )
            payload.update({"status": "retry_exhausted", "rows_claimable": False, "batch_terminal": True})
            state_path = _write_batch(root, payload)
            app = SimpleNamespace(resolved=_resolved_paths(root))

            missing_confirmation = request_network_rerun_row_retry(
                app=app,
                batch_id="batch-1",
                row_key="row-1",
                request_id="retry-request-unconfirmed",
                reason="This must remain blocked.",
            )
            first = request_network_rerun_row_retry(
                app=app,
                batch_id="batch-1",
                row_key="row-1",
                request_id="retry-request-1",
                reason="Source share restored and verified.",
                confirm_retry=True,
            )
            duplicate = request_network_rerun_row_retry(
                app=app,
                batch_id="batch-1",
                row_key="row-1",
                request_id="retry-request-1",
                reason="Duplicate delivery.",
                confirm_retry=True,
            )
            conflicting = request_network_rerun_row_retry(
                app=app,
                batch_id="batch-1",
                row_key="row-1",
                request_id="retry-request-2",
                reason="Second click.",
                confirm_retry=True,
            )

            self.assertFalse(missing_confirmation.ok)
            self.assertIn("confirm_retry_required", missing_confirmation.errors)
            self.assertTrue(first.ok)
            self.assertTrue(duplicate.ok)
            self.assertTrue(duplicate.data["idempotent"])
            self.assertFalse(conflicting.ok)
            self.assertIn("manual_retry_duplicate_guard", conflicting.errors)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            reopened = state["rows"][0]
            self.assertEqual(reopened["status"], "pending_claim")
            self.assertTrue(reopened["claimable"])
            self.assertEqual(reopened["retry_count"], 0)
            self.assertEqual(len(reopened["manual_retry_history"]), 1)
            self.assertEqual(reopened["first_failure"]["reason_code"], "source_access_failed")
            self.assertEqual(reopened["last_failure"]["reason_code"], "source_access_failed")
            self.assertEqual(state["status"], "active")
            self.assertTrue(state["rows_claimable"])

    def test_denied_manual_retry_request_id_remains_idempotently_denied_after_reconnect(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            payload = _state_payload(root, source=source)
            row = payload["rows"][0]
            row.update(
                {
                    "status": "retry_exhausted",
                    "claim_status": "retry_exhausted",
                    "claimable": False,
                    "terminal": True,
                    "retry_count": 3,
                    "retry_limit": 3,
                    "manual_recovery_required": True,
                    "manual_recovery_available": True,
                }
            )
            payload.update({"status": "retry_exhausted", "rows_claimable": False, "batch_terminal": True})
            _write_batch(root, payload)
            app = SimpleNamespace(resolved=_resolved_paths(root))
            offline_root = root / "Movies.offline"
            source.parent.rename(offline_root)

            first = request_network_rerun_row_retry(
                app=app,
                batch_id="batch-1",
                row_key="row-1",
                request_id="denied-request-1",
                reason="Share is still unavailable.",
                confirm_retry=True,
            )
            offline_root.rename(root / "Movies")
            duplicate = request_network_rerun_row_retry(
                app=app,
                batch_id="batch-1",
                row_key="row-1",
                request_id="denied-request-1",
                reason="Duplicate delivery after reconnect.",
                confirm_retry=True,
            )
            fresh = request_network_rerun_row_retry(
                app=app,
                batch_id="batch-1",
                row_key="row-1",
                request_id="accepted-request-2",
                reason="Fresh operator action after reconnect.",
                confirm_retry=True,
            )

            self.assertFalse(first.ok)
            self.assertFalse(duplicate.ok)
            self.assertTrue(duplicate.data["idempotent"])
            self.assertEqual(duplicate.data["request_id"], "denied-request-1")
            self.assertTrue(fresh.ok)

    def test_failure_with_output_requires_review_and_cannot_be_reclaimed(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app, state_path, completed, _source, output_path = _claim_row_for_reducer(
                root,
                job_id="job-failed-with-output",
            )
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"ambiguous-partial-output")
            request = _request_for_worker_failure(job_id="job-failed-with-output")
            request.output_path = str(output_path)
            request.output_size_bytes = output_path.stat().st_size

            updated = update_network_rerun_row_done(app=app, job=completed, request=request)
            retry = request_network_rerun_row_retry(
                app=app,
                batch_id="batch-1",
                row_key="row-1",
                request_id="retry-after-ambiguous-output",
                reason="Attempting retry must remain blocked.",
                confirm_retry=True,
            )
            reclaimed = claim_next_network_rerun_row(
                app=app,
                registry=InFlightRegistry(),
                worker_id="worker-2",
                worker_name="Worker 2",
                accessible_library_ids=["movies"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=False,
                job_id="job-duplicate-output",
            )

            self.assertTrue(updated)
            self.assertFalse(retry.ok)
            self.assertIsNone(reclaimed)
            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(row["status"], "review_required")
            self.assertEqual(row["reason_code"], "network_worker_failure_existing_output")
            self.assertFalse(row["manual_recovery_available"])
            self.assertTrue(output_path.is_file())

    def test_stale_done_cannot_overwrite_a_newer_active_claim(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            app, state_path, old_job, _source, _output_path = _claim_row_for_reducer(root, job_id="job-old")
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["rows"][0]["active_claim"] = {"job_id": "job-new", "worker_id": "worker-new"}
            state["rows"][0]["status"] = "claimed"
            state["rows"][0]["claim_status"] = "claimed"
            state_path.write_text(json.dumps(state), encoding="utf-8")
            request = _request_for_worker_failure(job_id="job-old")

            updated = update_network_rerun_row_done(app=app, job=old_job, request=request)

            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertFalse(updated)
            self.assertEqual(row["status"], "claimed")
            self.assertEqual(row["active_claim"]["job_id"], "job-new")
            self.assertEqual(row["active_claim"]["worker_id"], "worker-new")
            self.assertNotIn("reducer_result", row)

    def test_network_rerun_uses_the_existing_coordinator_retry_limit(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            state_path = _write_batch(root, _state_payload(root, source=source))
            app = SimpleNamespace(
                resolved=SimpleNamespace(
                    state_root=root / "State",
                    config_data={"CoordinatorMaxJobRetries": 2},
                )
            )
            registry = InFlightRegistry()
            lease = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-1",
                worker_name="Worker",
                accessible_library_ids=["movies"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=False,
                job_id="job-configured-retry-limit",
            )
            self.assertIsNotNone(lease)
            completed = registry.complete("job-configured-retry-limit", "worker-1", success=False)
            self.assertIsNotNone(completed)

            update_network_rerun_row_done(
                app=app,
                job=completed,
                request=_request_for_worker_failure(job_id="job-configured-retry-limit"),
            )

            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(row["retry_limit"], 2)
            self.assertEqual(row["retry_count"], 1)
            self.assertEqual(row["status"], "retry_scheduled")

    def test_stale_reaper_preserves_quarantine_as_durable_retry_schedule(self) -> None:
        class _OneSweepStop:
            def __init__(self) -> None:
                self.calls = 0

            def wait(self, _seconds: float) -> bool:
                self.calls += 1
                return self.calls > 1

        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            state_path = _write_batch(root, _state_payload(root, source=source))
            app = SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State"))
            registry = InFlightRegistry()
            lease = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-stale",
                worker_name="Stale Worker",
                accessible_library_ids=["movies"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=False,
                job_id="job-stale",
            )
            self.assertIsNotNone(lease)
            time.sleep(0.01)

            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._app = app
            dispatcher._registry = registry
            dispatcher._reaper_stop = _OneSweepStop()
            dispatcher._heartbeat_timeout_mins = lambda: 0.000001  # type: ignore[method-assign]
            dispatcher._inflight_state_path = lambda: root / "State" / "coordinator_inflight.json"  # type: ignore[method-assign]
            dispatcher._safe_log_cluster_event = lambda *_args, **_kwargs: None  # type: ignore[method-assign]

            CoordinatorDispatcher._reaper_loop(dispatcher)

            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(registry.active_count, 0)
            self.assertEqual(row["status"], "retry_scheduled")
            self.assertEqual(row["claim_status"], "retry_scheduled")
            self.assertTrue(row["claimable"])
            self.assertNotIn("active_claim", row)
            self.assertIn("stale", row["last_release"]["reason"].lower())
            self.assertGreater(
                datetime.fromisoformat(row["next_retry_at_utc"]),
                datetime.now(UTC),
            )
            immediate = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-next",
                worker_name="Next Worker",
                accessible_library_ids=["movies"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=False,
                job_id="job-too-early",
            )
            self.assertIsNone(immediate)
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["rows"][0]["next_retry_at_utc"] = (
                datetime.now(UTC) - timedelta(seconds=1)
            ).isoformat()
            state_path.write_text(json.dumps(state), encoding="utf-8")
            with registry._lock:
                registry._recent_completions.clear()
                for entry in registry._reclaimed_source_quarantine.values():
                    entry["expires_at"] = (
                        datetime.now(UTC) - timedelta(seconds=1)
                    ).isoformat()
            due = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-next",
                worker_name="Next Worker",
                accessible_library_ids=["movies"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=False,
                job_id="job-after-quarantine",
            )
            duplicate = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-third",
                worker_name="Third Worker",
                accessible_library_ids=["movies"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=False,
                job_id="job-duplicate-after-quarantine",
            )
            self.assertIsNotNone(due)
            self.assertIsNone(duplicate)

    def test_orphaned_destination_policy_intent_is_reconciled_to_review_without_replay(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            payload = _state_payload(root, source=source, destination_policy_enabled=True)
            row = payload["rows"][0]
            row.update(
                {
                    "status": "destination_policy_applying",
                    "claim_status": "destination_policy_applying",
                    "claimable": False,
                    "terminal": False,
                    "destination_policy_operation_id": "destination-op-crashed",
                }
            )
            state_path = _write_batch(root, payload)
            app = SimpleNamespace(resolved=_resolved_paths(root))

            with mock.patch.object(rerun_claims_module, "apply_network_rerun_destination_policy") as apply_policy:
                reconciled = rerun_claims_module.reconcile_orphaned_network_rerun_destination_policies(app)

            self.assertEqual(reconciled, 1)
            apply_policy.assert_not_called()
            recovered = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(recovered["status"], "review_required")
            self.assertTrue(recovered["terminal"])
            self.assertEqual(
                recovered["reason_code"],
                "network_destination_policy_outcome_ambiguous_after_restart",
            )

    def test_slow_destination_policy_does_not_hold_global_batch_state_lock(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source_one = root / "Movies" / "Movie1.mkv"
            source_two = root / "Movies" / "Movie2.mkv"
            source_one.parent.mkdir(parents=True)
            source_one.write_bytes(b"source-one")
            source_two.write_bytes(b"source-two")
            first = _state_payload(root, source=source_one, destination_policy_enabled=True)
            first_path = _write_batch(root, first)
            second = _state_payload(root, source=source_two)
            second["batch_id"] = "batch-2"
            second["rows"][0]["row_key"] = "row-2"
            second["rows"][0]["planned_output_path"] = str(root / "Handoff" / "batch-2" / "row-2")
            second["rows"][0]["output_handoff"]["planned_row_handoff_path"] = second["rows"][0]["planned_output_path"]
            second_path = root / "State" / "Rerun" / "Network" / "batch-2.json"
            second_path.write_text(json.dumps(second), encoding="utf-8")
            app = SimpleNamespace(resolved=_resolved_paths(root), product_version="test-version")
            registry = InFlightRegistry()
            first_lease = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-1",
                worker_name="Worker 1",
                accessible_library_ids=["movies"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=False,
                job_id="job-slow-policy",
            )
            self.assertIsNotNone(first_lease)
            completed = registry.complete("job-slow-policy", "worker-1", success=True)
            self.assertIsNotNone(completed)
            output = root / "Handoff" / "batch-1" / "row-1" / source_one.name
            output.parent.mkdir(parents=True)
            output.write_bytes(b"output")
            artifact = _write_worker_result_artifact(root, job_id="job-slow-policy", output_path=output)
            request = _request_for_worker_done(job_id="job-slow-policy", output_path=output, artifact_path=artifact)
            entered = threading.Event()
            release = threading.Event()

            def slow_policy(*_args: object, **_kwargs: object) -> dict[str, object]:
                entered.set()
                release.wait(timeout=5)
                return {
                    "schema_version": rerun_claims_module.NETWORK_RERUN_DESTINATION_POLICY_RESULT_SCHEMA_VERSION,
                    "ok": True,
                    "action": "review_workspace",
                    "status": "review_workspace",
                    "terminal": True,
                    "reason_code": "network_rerun_review_workspace",
                }

            update_thread = threading.Thread(
                target=lambda: update_network_rerun_row_done(app=app, job=completed, request=request)
            )
            claimed: list[object] = []
            try:
                with mock.patch.object(
                    rerun_claims_module,
                    "apply_network_rerun_destination_policy",
                    side_effect=slow_policy,
                ):
                    update_thread.start()
                    self.assertTrue(entered.wait(timeout=1))
                    claim_thread = threading.Thread(
                        target=lambda: claimed.append(
                            claim_next_network_rerun_row(
                                app=app,
                                registry=registry,
                                worker_id="worker-2",
                                worker_name="Worker 2",
                                accessible_library_ids=["movies"],
                                encode_config_for_row=lambda _record: {},
                                allow_local_handoff=False,
                                job_id="job-other-batch",
                            )
                        )
                    )
                    claim_thread.start()
                    claim_thread.join(timeout=2.0)
                    completed_before_release = not claim_thread.is_alive()
                    release.set()
                    claim_thread.join(timeout=2)
                    update_thread.join(timeout=2)
            finally:
                release.set()
                update_thread.join(timeout=2)

            self.assertTrue(completed_before_release)
            self.assertTrue(claimed and claimed[0] is not None)
            finalized = json.loads(first_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertEqual(finalized["status"], "review_workspace")
            self.assertEqual(
                [event["state"] for event in finalized["timeline"]][-2:],
                ["destination_policy_applying", "review_workspace"],
            )

    def test_worker_artifact_and_output_probes_project_timeout_without_direct_path_access(self) -> None:
        with mock.patch.object(
            rerun_claims_module,
            "run_source_probe",
            side_effect=TimeoutError("probe timed out"),
        ) as probe:
            artifact, payload = rerun_claims_module._read_worker_result_artifact(r"\\server\share\worker_result.json")
            output = rerun_claims_module._output_evidence(
                SimpleNamespace(output_path=r"\\server\share\Movie.mkv", output_size_bytes=0),
                r"\\server\share",
            )

        self.assertIsNone(payload)
        self.assertEqual(artifact["status"], "legacy_path_unavailable")
        self.assertFalse(artifact["supplied"])
        self.assertEqual(output["probe_status"], "access_failed")
        self.assertTrue(output["stale"])
        self.assertEqual(probe.call_count, 1)

    def test_inline_worker_result_evidence_prevents_worker_local_path_probe(self) -> None:
        inline = {
            "SchemaVersion": "local_worker_result.v1",
            "JobKind": "csv_rerun_row",
            "RerunBatchId": "batch-1",
            "RerunRowKey": "row-1",
            "WorkerClaimId": "job-inline",
            "Success": True,
            "Status": "processed",
            "OutputPath": r"\\server\handoff\batch-1\row-1\Movie.mkv",
            "OutputSizeBytes": 123,
            "PublishState": "published",
            "PublishMode": "handoff",
            "Route": "network_lifecycle_single_file",
        }
        worker_local_path = r"D:\WorkerState\NetworkWorkerResults\job-inline\result.json"
        with mock.patch.object(rerun_claims_module, "_killable_source_probe") as probe:
            evidence, payload = rerun_claims_module._read_worker_result_artifact(
                worker_local_path,
                inline_payload=inline,
            )
        probe.assert_not_called()
        self.assertEqual(payload, inline)
        self.assertTrue(evidence["valid"])
        self.assertEqual(evidence["transport"], "inline_signed_request")

        with mock.patch.object(rerun_claims_module, "_killable_source_probe") as probe:
            legacy_evidence, legacy_payload = rerun_claims_module._read_worker_result_artifact(
                worker_local_path
            )
        probe.assert_not_called()
        self.assertIsNone(legacy_payload)
        self.assertEqual(legacy_evidence["status"], "legacy_path_unavailable")
        self.assertFalse(legacy_evidence["supplied"])

    def test_late_stale_release_cannot_clear_a_newer_network_rerun_claim(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            state_path = _write_batch(root, _state_payload(root, source=source))
            app = SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State"))
            registry = InFlightRegistry()
            old_lease = claim_next_network_rerun_row(
                app=app,
                registry=registry,
                worker_id="worker-old",
                worker_name="Old Worker",
                accessible_library_ids=["movies"],
                encode_config_for_row=lambda _record: {},
                allow_local_handoff=False,
                job_id="job-old",
            )
            self.assertIsNotNone(old_lease)
            old_job = registry.unclaim("job-old", "worker-old")
            self.assertIsNotNone(old_job)
            self.assertTrue(
                update_network_rerun_row_released(
                    app=app,
                    job=old_job,
                    worker_id="worker-old",
                    reason="first release",
                )
            )
            state = json.loads(state_path.read_text(encoding="utf-8"))
            state["rows"][0].update(
                {
                    "status": "claimed",
                    "claim_status": "claimed",
                    "claimable": False,
                    "active_claim": {
                        "job_id": "job-new",
                        "worker_id": "worker-new",
                        "worker_name": "New Worker",
                    },
                }
            )
            state_path.write_text(json.dumps(state), encoding="utf-8")

            released = update_network_rerun_row_released(
                app=app,
                job=old_job,
                worker_id="worker-old",
                reason="late stale release",
            )

            row = json.loads(state_path.read_text(encoding="utf-8"))["rows"][0]
            self.assertFalse(released)
            self.assertEqual(row["status"], "claimed")
            self.assertFalse(row["claimable"])
            self.assertEqual(row["active_claim"]["job_id"], "job-new")
            self.assertEqual(row["active_claim"]["worker_id"], "worker-new")

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
