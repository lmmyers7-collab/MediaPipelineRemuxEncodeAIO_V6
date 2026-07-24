from __future__ import annotations

from datetime import datetime, UTC
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from mediapipeline.core.kernel.contracts import accepted_run_rows_fingerprint
from mediapipeline.core.paths.queue_input_fingerprint import queue_input_fingerprint
from mediapipeline.core.processes.lifecycle_lease import LifecycleLeaseStore
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from tests.python.desktop.application_facade_test_support import DummyWorkflowFacadeService, _resolved


FIXED_NOW = datetime(2026, 7, 20, 12, 0, 0, tzinfo=UTC)


class QueueLaunchHarness:
    def __init__(self, root: Path) -> None:
        self.root = root
        self.service = DummyWorkflowFacadeService(root)
        self.service.queue_snapshot_freshness_wall_now = lambda: FIXED_NOW  # type: ignore[method-assign]
        self.service.queue_snapshot_freshness_monotonic_now = lambda: 100.0  # type: ignore[method-assign]
        self.facade = MediaPipelineApplicationFacade(self.service, app_version="v5-test")
        self.resolved = _resolved(root)
        self.resolved.local_base = root / "LocalBase"
        self.resolved.state_root = self.resolved.local_base / "State"
        self.resolved.source_movies = root / "Movies"
        self.resolved.source_tv = root / "TV"
        self.resolved.queue_snapshot_path = self.resolved.state_root / "Progress" / "queue_snapshot.json"
        self.resolved.priority_manifest_path = self.resolved.state_root / "Queue" / "priority.json"
        self.resolved.queue_strategy_path = self.resolved.state_root / "Queue" / "strategy.json"
        self.resolved.file_overrides_path = self.resolved.state_root / "Queue" / "file_overrides.json"
        self.resolved.config_data = {
            "NetworkRole": "standalone",
            "SourceMovies": str(self.resolved.source_movies),
            "SourceTV": str(self.resolved.source_tv),
            "Outsource": str(root / "Outsource"),
            "QueueLaunchSnapshotFreshnessSeconds": 60,
            "LibraryProfiles": [{"id": "anime", "source_path": str(root / "Anime")}],
        }
        for directory in (
            self.resolved.source_movies,
            self.resolved.source_tv,
            root / "Outsource",
            root / "Anime",
            self.resolved.queue_snapshot_path.parent,
            self.resolved.priority_manifest_path.parent,
        ):
            assert directory is not None
            directory.mkdir(parents=True, exist_ok=True)
        self.input_documents = {
            self.resolved.config_path: "@{ NetworkRole = 'standalone'; LibraryProfiles = @(@{ id = 'anime' }) }",
            self.resolved.priority_manifest_path: '{"priority": [], "hold": []}',
            self.resolved.queue_strategy_path: '{"strategy": "priority_then_oldest", "manual_order": []}',
            self.resolved.file_overrides_path: '{"files": {}}',
        }
        self.restore_inputs()

    def restore_inputs(self) -> None:
        for path, content in self.input_documents.items():
            assert path is not None
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

    @property
    def snapshot_path(self) -> Path:
        assert self.resolved.queue_snapshot_path is not None
        return self.resolved.queue_snapshot_path

    @property
    def status_path(self) -> Path:
        assert self.resolved.state_root is not None
        return self.resolved.state_root / "Progress" / "queue_scan_status.json"

    def write_snapshot(
        self,
        *,
        request_id: str = "request-stable",
        status_request_id: str | None = None,
        scan_status: str = "completed",
        scan_mode: str = "inventory_then_curate",
        origin: str = "dry_run",
        config_path: Path | None = None,
        produced_at: str | None = None,
        plan_fingerprint: str = "plan-stable",
        pending_health: dict[str, object] | None = None,
        pending_backpressure: dict[str, object] | None = None,
    ) -> dict[str, object]:
        source_path = self.resolved.source_movies / "Movie.mkv"  # type: ignore[operator]
        accepted_rows = [
            {
                "source_identity": "source-identity-stable",
                "source_identity_algorithm": "path_size_mtime_sha256.v1",
                "source_path": str(source_path),
                "display_name": "Movie (2026).mkv",
                "planned_display_name": "Movie (2026).mkv",
                "planned_display_name_source": "plex_destination_plan.v1",
                "parent_context": str(self.resolved.source_movies),
                "run_queue_index": 1,
                "run_queue_total": 1,
                "route": "remux",
                "route_reason_code": "copy_compatible",
                "route_reason": "Already compatible",
                "intended_final_path": str(self.root / "Outsource" / "Movie (2026).mkv"),
            }
        ]
        input_fingerprint = queue_input_fingerprint(self.resolved)
        payload: dict[str, object] = {
            "schema_version": "queue_plan_snapshot.v1",
            "produced_at": produced_at or FIXED_NOW.isoformat(),
            "config_path": str(config_path or self.resolved.config_path),
            "local_base": str(self.resolved.local_base),
            "source_movies": str(self.resolved.source_movies),
            "source_tv": str(self.resolved.source_tv),
            "outsource": str(self.root / "Outsource"),
            "movie_count_total": 1,
            "tv_count_total": 0,
            "priority_count": 0,
            "runnable_count": 1,
            "queue_snapshot_origin": origin,
            "desktop_queue_preview_request_id": request_id,
            "queue_input_fingerprint_schema": input_fingerprint["schema_version"],
            "queue_input_fingerprint": input_fingerprint["fingerprint"],
            "queue_input_components": input_fingerprint["components"],
            "queue_plan_fingerprint_schema": "queue_plan_fingerprint.v1",
            "queue_plan_fingerprint": plan_fingerprint,
            "accepted_run_rows_fingerprint_schema": "accepted_run_rows_fingerprint.v1",
            "accepted_run_rows_fingerprint": accepted_run_rows_fingerprint(accepted_rows),
            "pending_publish_index_health": pending_health or {"status": "ready"},
            "pending_publish_backpressure": pending_backpressure or {"blocked": False},
            "accepted_run_rows": accepted_rows,
            "rows": [
                {
                    "global_order": 1,
                    "phase": "movie",
                    "media_kind": "movie",
                    "queue_index": 1,
                    "queue_total": 1,
                    "is_priority": False,
                    "source_path": str(source_path),
                    "root_path": str(self.resolved.source_movies),
                    "relative_path": "Movie.mkv",
                    "display_name": "Movie (2026).mkv",
                    "size_gb": 1.0,
                    "route": "remux",
                    "route_reason_code": "copy_compatible",
                    "route_reason": "Already compatible",
                    "blocked_reason": "",
                }
            ],
        }
        self.snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
        os.utime(self.snapshot_path, (FIXED_NOW.timestamp(), FIXED_NOW.timestamp()))
        self.status_path.write_text(
            json.dumps(
                {
                    "schema_version": "desktop_queue_scan_status.v1",
                    "scan_id": "scan-stable",
                    "status": scan_status,
                    "phase": "complete" if scan_status == "completed" else scan_status,
                    "mode": scan_mode,
                    "queue_preview_request_id": status_request_id or request_id,
                }
            ),
            encoding="utf-8",
        )
        return payload

    def check(self, *, retain_accepted_rows: bool = False) -> dict[str, object]:
        return self.facade._normal_queue_scope_preflight_check(  # type: ignore[attr-defined]
            self.resolved,
            retain_accepted_rows=retain_accepted_rows,
        )


class QueueSnapshotLaunchPolicyTests(unittest.TestCase):
    def test_blank_run_once_rejects_each_invalid_snapshot_dimension_with_rescan_guidance(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            harness = QueueLaunchHarness(Path(raw_root))
            cases: list[tuple[str, callable, str]] = [
                (
                    "scope_mismatch",
                    lambda: harness.write_snapshot(config_path=harness.root / "other.psd1"),
                    "queue_snapshot_scope_mismatch",
                ),
                (
                    "wrong_origin",
                    lambda: harness.write_snapshot(origin="active_run"),
                    "queue_snapshot_origin_not_dry_run",
                ),
                (
                    "plan_fingerprint_missing",
                    lambda: harness.write_snapshot(plan_fingerprint=""),
                    "queue_plan_fingerprint_missing",
                ),
            ]
            for label, arrange, expected_reason in cases:
                with self.subTest(label=label):
                    harness.restore_inputs()
                    arrange()
                    check = harness.check()
                    self.assertEqual(check["status"], "blocked")
                    self.assertIn(expected_reason, check["detail"])
                    self.assertRegex(str(check["action"]), r"(?i)(run|refresh).*(queue|scan)")

            harness.restore_inputs()
            harness.write_snapshot(produced_at="2026-07-20T12:00:00")
            timestamp_advisory = harness.check()
            self.assertEqual(timestamp_advisory["status"], "ready")
            self.assertIn("preview_age_policy=advisory", timestamp_advisory["detail"])
            self.assertIn("preview_age=unavailable", timestamp_advisory["detail"])
            self.assertNotIn("queue_snapshot_timezone_missing", timestamp_advisory["detail"])

            harness.write_snapshot()
            harness.snapshot_path.write_text("{malformed", encoding="utf-8")
            malformed = harness.check()
            self.assertEqual(malformed["status"], "blocked")
            self.assertIn("queue_snapshot_unreadable", malformed["detail"])
            self.assertRegex(str(malformed["action"]), r"(?i)refresh.*queue")

            harness.write_snapshot()
            valid = harness.check(retain_accepted_rows=True)
            self.assertEqual(valid["status"], "ready")
            self.assertEqual(valid["queue_plan_fingerprint"], "plan-stable")
            self.assertEqual(len(valid["_accepted_run_rows"]), 1)

    def test_scan_status_and_request_identity_are_not_launch_authority(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            harness = QueueLaunchHarness(Path(raw_root))
            cases = (
                {
                    "scan_status": "running",
                    "scan_mode": "inventory_then_curate",
                    "status_request_id": "request-running-scan",
                },
                {
                    "scan_status": "running",
                    "scan_mode": "inventory_only",
                    "status_request_id": "request-transient-inventory",
                },
                {
                    "scan_status": "completed",
                    "scan_mode": "inventory_only",
                    "status_request_id": "request-completed-inventory",
                },
            )
            for case in cases:
                with self.subTest(**case):
                    harness.write_snapshot(**case)
                    harness.service.queue_source_scan_active_block_message = (  # type: ignore[method-assign]
                        lambda _action: "Queue scan is running."
                    )
                    check = harness.check(retain_accepted_rows=True)
                    self.assertEqual(check["status"], "ready")
                    self.assertEqual(check["queue_plan_fingerprint"], "plan-stable")
                    self.assertEqual(len(check["_accepted_run_rows"]), 1)
                    self.assertNotIn("queue_scan", str(check["detail"]))
                    self.assertNotIn("request_mismatch", str(check["detail"]))

    def test_queue_input_changes_name_the_exact_component_and_require_rescan(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            harness = QueueLaunchHarness(Path(raw_root))
            changes = (
                ("config", harness.resolved.config_path, "@{ LibraryProfiles = @(@{ id = 'changed' }) }"),
                ("priority_manifest", harness.resolved.priority_manifest_path, '{"priority": ["Movie.mkv"], "hold": []}'),
                ("queue_strategy", harness.resolved.queue_strategy_path, '{"strategy": "manual", "manual_order": ["Movie.mkv"]}'),
                ("file_overrides", harness.resolved.file_overrides_path, '{"files": {"Movie.mkv": {"route": "encode"}}}'),
            )
            for component, path, replacement in changes:
                with self.subTest(component=component):
                    harness.restore_inputs()
                    harness.write_snapshot()
                    assert path is not None
                    path.write_text(replacement, encoding="utf-8")
                    check = harness.check()
                    self.assertEqual(check["status"], "blocked")
                    self.assertIn("queue_snapshot_inputs_not_current", check["detail"])
                    self.assertIn(f"queue_input_mismatch:{component}", check["detail"])
                    self.assertIn(component, str(check["evidence"]))
                    self.assertIn("Run Queue scan again", str(check["action"]))

    def test_pending_publish_posture_and_accepted_membership_contradictions_block(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            harness = QueueLaunchHarness(Path(raw_root))
            harness.write_snapshot(pending_health={"status": "blocked", "reason": "index unreadable"})
            health = harness.check()
            harness.write_snapshot(
                pending_backpressure={"blocked": True, "block_reason": "deferred threshold reached"}
            )
            backpressure = harness.check()
            payload = harness.write_snapshot()
            payload["accepted_run_rows_fingerprint"] = "tampered"
            harness.snapshot_path.write_text(json.dumps(payload), encoding="utf-8")
            os.utime(harness.snapshot_path, (FIXED_NOW.timestamp(), FIXED_NOW.timestamp()))
            membership = harness.check()

        self.assertIn("pending_publish_index_blocked", health["detail"])
        self.assertIn("pending_publish_backpressure_blocked", backpressure["detail"])
        self.assertIn("queue_snapshot_accepted_fingerprint_mismatch", membership["detail"])
        for check in (health, backpressure, membership):
            self.assertEqual(check["status"], "blocked")
            self.assertRegex(str(check["action"]), r"(?i)(run|refresh).*(queue|scan)")

    def test_start_revalidates_unsafe_snapshot_replacement_inside_durable_launch_lease(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            harness = QueueLaunchHarness(Path(raw_root))
            harness.write_snapshot()
            self.assertEqual(harness.check()["status"], "ready")
            original_check = harness.facade._normal_queue_scope_preflight_check  # type: ignore[attr-defined]
            lease_evidence: list[dict[str, object]] = []

            def replace_then_validate(*args, **kwargs):
                assert harness.resolved.state_root is not None
                lease_evidence.append(LifecycleLeaseStore(harness.resolved.state_root).status())
                replacement = json.loads(harness.snapshot_path.read_text(encoding="utf-8"))
                replacement["queue_snapshot_origin"] = "active_run"
                harness.snapshot_path.write_text(json.dumps(replacement), encoding="utf-8")
                os.utime(harness.snapshot_path, (FIXED_NOW.timestamp(), FIXED_NOW.timestamp()))
                return original_check(*args, **kwargs)

            with patch.object(
                harness.facade,
                "_normal_queue_scope_preflight_check",
                side_effect=replace_then_validate,
            ):
                result = harness.facade.start_pipeline_process(
                    harness.resolved,
                    {"mode": "once", "_command_id": "command-stable"},
                ).to_mapping()

        self.assertFalse(result["ok"])
        self.assertIn("not a backend dry-run", result["message"])
        self.assertEqual(len(lease_evidence), 1)
        self.assertEqual(lease_evidence[0]["status"], "active")
        self.assertEqual(lease_evidence[0]["lease"]["scope"], "Pipeline start")
        self.assertFalse(hasattr(harness.service, "started_pipeline"))

    def test_scan_racing_run_once_preempts_inventory_before_curation_without_weakening_other_guards(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            inventory_started = threading.Event()
            release_inventory = threading.Event()

            class InventoryScanService(DummyWorkflowFacadeService):
                def _queue_scan_id(self) -> str:
                    return "scan-race-stable"

            def blocking_inventory(_resolved, *, scan_id: str):
                inventory_started.set()
                release_inventory.wait(timeout=3.0)
                return {
                    "schema_version": "desktop_queue_source_inventory.v1",
                    "scan_id": scan_id,
                    "row_count": 0,
                    "warnings": [],
                    "rows": [],
                }

            harness = QueueLaunchHarness(root)
            service = InventoryScanService(root)
            service.queue_snapshot_freshness_wall_now = lambda: FIXED_NOW  # type: ignore[method-assign]
            service.queue_snapshot_freshness_monotonic_now = lambda: 100.0  # type: ignore[method-assign]
            harness.service = service
            harness.facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            harness.write_snapshot()
            with patch(
                "mediapipeline.core.queue.service.build_queue_source_inventory",
                side_effect=blocking_inventory,
            ):
                scan = service.start_queue_source_scan(
                    harness.resolved,
                    {"mode": "inventory_then_curate", "force": True, "scope": "all"},
                )
                self.assertTrue(inventory_started.wait(timeout=2.0))
                active = getattr(service, "_queue_source_scan_active", None)
                thread = active.get("thread") if isinstance(active, dict) else None
                try:
                    validate = harness.facade.start_pipeline_process(
                        harness.resolved,
                        {"mode": "validate"},
                    ).to_mapping()
                    single_file = harness.resolved.source_movies / "Single.mkv"  # type: ignore[operator]
                    single_file.write_bytes(b"media")
                    scoped_once = harness.facade.start_pipeline_process(
                        harness.resolved,
                        {"mode": "once", "single_file": str(single_file)},
                    ).to_mapping()
                    priority_once = harness.facade.start_pipeline_process(
                        harness.resolved,
                        {
                            "mode": "once",
                            "queue_scope": "priority_export",
                            "priority_export_id": "missing-export",
                        },
                    ).to_mapping()
                    preflight = harness.facade.get_launch_preflight(
                        harness.resolved,
                        {"target": "pipeline", "mode": "once"},
                    )
                    run_once = harness.facade.start_pipeline_process(
                        harness.resolved,
                        {"mode": "once", "_command_id": "command-scan-race"},
                    ).to_mapping()
                finally:
                    proc = getattr(service, "started_pipeline_proc", None)
                    if proc is not None:
                        proc.complete()
                    release_inventory.set()
                    if isinstance(thread, threading.Thread):
                        thread.join(timeout=2.0)
                scan_status = service.read_queue_scan_status(harness.resolved)

        self.assertTrue(scan["ok"])
        for blocked in (validate, scoped_once, priority_once):
            self.assertFalse(blocked["ok"])
            self.assertIn("queue source scan", blocked["message"])
        preflight_checks = {
            str(check["key"]): check
            for check in preflight["checks"]
        }
        self.assertTrue(preflight["can_request_start"])
        self.assertEqual(preflight_checks["active_work"]["status"], "ready")
        self.assertEqual(preflight_checks["normal_queue_scope"]["status"], "ready")
        self.assertTrue(run_once["ok"])
        self.assertEqual(run_once["data"]["accepted_queue_fingerprint"], "plan-stable")
        self.assertEqual(scan_status["status"], "deferred")

    def test_scan_already_curating_blocks_normal_run_once_preflight_and_start(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)

            class CuratingScanService(DummyWorkflowFacadeService):
                def __init__(self, service_root: Path) -> None:
                    super().__init__(service_root)
                    self.curate_started = threading.Event()
                    self.release_curate = threading.Event()

                def _queue_scan_id(self) -> str:
                    return "scan-curating-stable"

                def build_queue_preview(self, _resolved, force_refresh: bool = False):
                    _ = force_refresh
                    self.curate_started.set()
                    self.release_curate.wait(timeout=3.0)
                    return []

            harness = QueueLaunchHarness(root)
            service = CuratingScanService(root)
            harness.service = service
            harness.facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            harness.write_snapshot()
            scan = service.start_queue_source_scan(
                harness.resolved,
                {"mode": "inventory_then_curate", "force": True, "scope": "all"},
            )
            self.assertTrue(service.curate_started.wait(timeout=2.0))
            active = getattr(service, "_queue_source_scan_active", None)
            thread = active.get("thread") if isinstance(active, dict) else None
            try:
                preflight = harness.facade.get_launch_preflight(
                    harness.resolved,
                    {"target": "pipeline", "mode": "once"},
                )
                run_once = harness.facade.start_pipeline_process(
                    harness.resolved,
                    {"mode": "once", "_command_id": "command-curating-race"},
                ).to_mapping()
            finally:
                service.release_curate.set()
                if isinstance(thread, threading.Thread):
                    thread.join(timeout=2.0)

        preflight_checks = {
            str(check["key"]): check
            for check in preflight["checks"]
        }
        self.assertTrue(scan["ok"])
        self.assertFalse(preflight["can_request_start"])
        self.assertEqual(preflight_checks["active_work"]["status"], "blocked")
        self.assertIn("queue source scan", str(preflight_checks["active_work"]["evidence"]))
        self.assertFalse(run_once["ok"])
        self.assertIn("queue source scan", run_once["message"])

    def test_csv_rerun_and_network_roles_do_not_enter_standard_queue_contract(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            harness = QueueLaunchHarness(Path(raw_root))
            csv_path = harness.root / "rerun.csv"
            csv_path.write_text("enabled,source_path\n", encoding="utf-8")
            rerun = harness.facade.get_launch_preflight(
                harness.resolved,
                {"target": "rerun", "csv_path": str(csv_path)},
            )
            rerun_keys = {str(check.get("key")) for check in rerun["checks"]}
            coordinator = harness.resolved
            coordinator.config_data = dict(coordinator.config_data, NetworkRole="coordinator")
            with patch.object(
                harness.facade,
                "_normal_queue_scope_preflight_check",
                side_effect=AssertionError("network launch must not enter standard Queue preflight"),
            ):
                network = harness.facade.start_pipeline_process(
                    coordinator,
                    {"mode": "once"},
                ).to_mapping()

        self.assertNotIn("normal_queue_scope", rerun_keys)
        self.assertEqual(rerun["target"], "rerun")
        self.assertFalse(network["ok"])
        self.assertEqual(network["refresh_hint"], "network")


if __name__ == "__main__":
    unittest.main()
