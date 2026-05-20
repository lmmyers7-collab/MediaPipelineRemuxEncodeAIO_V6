from __future__ import annotations

from datetime import datetime, timedelta
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade
from DesktopApp.tests.test_application_facade import DummyProc, DummyWorkflowFacadeService, _resolved


class ApplicationFacadeProcessLaunchTests(unittest.TestCase):
    def test_pipeline_start_uses_existing_service_launch_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            result = facade.start_pipeline_process(
                resolved,
                {
                    "mode": "validate",
                    "sleep_seconds": 5,
                    "show_config": True,
                    "show_console": False,
                    "single_file": str(root / "sample.mkv"),
                },
            ).to_mapping()
            rejected = facade.start_pipeline_process(resolved, {"mode": "once", "extra_args": "-Danger"}).to_mapping()

        self.assertTrue(result["ok"])
        self.assertEqual(result["schema_version"], "desktop_command_result.v1")
        self.assertEqual(result["command"], "pipeline.start")
        self.assertEqual(result["data"]["mode"], "validate")
        self.assertEqual(result["data"]["pid"], 24680)
        self.assertEqual(service.started_pipeline["mode"], "validate")
        self.assertEqual(service.started_pipeline["sleep_seconds"], 5)
        self.assertEqual(service.started_pipeline["single_file"], str(root / "sample.mkv"))
        self.assertFalse(rejected["ok"])
        self.assertIn("Extra pipeline arguments", rejected["message"])

    def test_pipeline_start_respects_schedule_gate_before_web_launch_ui(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            service.save_app_state({"schedule_enabled": True, "schedule_grid": service.default_schedule_grid()})
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            blocked = facade.start_pipeline_process(resolved, {"mode": "continuous"}).to_mapping()
            run_once = facade.start_pipeline_process(
                resolved,
                {"mode": "continuous", "schedule_override": "run_once"},
            ).to_mapping()
            ignored = facade.start_pipeline_process(
                resolved,
                {"mode": "continuous", "schedule_override": "ignore"},
            ).to_mapping()

        self.assertFalse(blocked["ok"])
        self.assertIn("outside the allowed schedule", blocked["message"])
        self.assertEqual(blocked["refresh_hint"], "schedule")
        self.assertTrue(run_once["ok"])
        self.assertEqual(run_once["data"]["requested_mode"], "continuous")
        self.assertEqual(run_once["data"]["mode"], "once")
        self.assertEqual(run_once["data"]["schedule"]["override"], "run_once")
        self.assertTrue(ignored["ok"])
        self.assertEqual(ignored["data"]["mode"], "continuous")

    def test_pipeline_start_allows_scheduled_continuous_with_backend_watcher_available(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            grid = {day: [True] * 48 for day in service.default_schedule_grid()}
            service.save_app_state({"schedule_enabled": True, "schedule_grid": grid})
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            continuous = facade.start_pipeline_process(resolved, {"mode": "continuous"}).to_mapping()
            once = facade.start_pipeline_process(resolved, {"mode": "once"}).to_mapping()

        self.assertTrue(continuous["ok"])
        self.assertEqual(continuous["data"]["mode"], "continuous")
        self.assertIn("no stop boundary", " ".join(continuous["data"]["launch_prep"]))
        self.assertTrue(once["ok"])
        self.assertEqual(once["data"]["mode"], "once")

    def test_audit_start_uses_existing_service_launch_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"Outsource": str(root / "Outsource")}

            result = facade.start_audit_process(resolved, {"include_sidecars": True}).to_mapping()

        self.assertTrue(result["ok"])
        self.assertEqual(result["schema_version"], "desktop_command_result.v1")
        self.assertEqual(result["command"], "audit.start")
        self.assertEqual(result["data"]["pid"], 24681)
        self.assertTrue(service.started_audit["include_sidecars"])
        self.assertEqual(service.started_audit["library_root"], str(root / "Outsource"))

    def test_rerun_start_uses_existing_service_launch_path(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            csv_path.write_text("enabled,source_path\ntrue,C:\\Media\\Movie.mkv\n", encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            result = facade.start_rerun_csv_process(resolved, {"csv_path": str(csv_path)}).to_mapping()
            rejected = facade.start_rerun_csv_process(
                resolved,
                {"csv_path": str(csv_path), "original_mode": "delete"},
            ).to_mapping()
            missing = facade.start_rerun_csv_process(resolved, {}).to_mapping()

        self.assertTrue(result["ok"])
        self.assertEqual(result["schema_version"], "desktop_command_result.v1")
        self.assertEqual(result["command"], "rerun.start")
        self.assertEqual(result["data"]["pid"], 24682)
        self.assertFalse(result["data"]["dry_run"])
        self.assertEqual(service.started_rerun["return_mode"], "park")
        self.assertFalse(rejected["ok"])
        self.assertIn("copy/keep/park", rejected["message"])
        self.assertFalse(missing["ok"])
        self.assertIn("csv_path", missing["message"])

    def test_process_launch_commands_share_backend_launch_lock(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            csv_path.write_text("enabled,source_path\ntrue,C:\\Media\\Movie.mkv\n", encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"Outsource": str(root / "Outsource")}

            self.assertTrue(facade._process_launch_lock.acquire(blocking=False))  # type: ignore[attr-defined]
            try:
                pipeline = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()
                audit = facade.start_audit_process(resolved, {}).to_mapping()
                rerun = facade.start_rerun_csv_process(resolved, {"csv_path": str(csv_path)}).to_mapping()
            finally:
                facade._process_launch_lock.release()  # type: ignore[attr-defined]

        self.assertFalse(pipeline["ok"])
        self.assertFalse(audit["ok"])
        self.assertFalse(rerun["ok"])
        self.assertIn("another process launch command is already in progress", pipeline["message"])
        self.assertIn("another process launch command is already in progress", audit["message"])
        self.assertIn("another process launch command is already in progress", rerun["message"])
        self.assertFalse(hasattr(service, "started_pipeline"))
        self.assertFalse(hasattr(service, "started_audit"))
        self.assertFalse(hasattr(service, "started_rerun"))

    def test_pipeline_start_rejects_duplicate_launch_when_first_process_is_still_running(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            start_calls: list[dict[str, object]] = []

            def fake_start_pipeline(**kwargs: object) -> DummyProc:
                start_calls.append(dict(kwargs))
                return DummyProc(25000 + len(start_calls))

            service.start_pipeline = fake_start_pipeline  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            first = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()
            service.find_related_pipeline_processes = lambda _resolved: [DummyProc(first["data"]["pid"])]  # type: ignore[method-assign]
            second = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()

        self.assertTrue(first["ok"])
        self.assertEqual(first["data"]["pid"], 25001)
        self.assertFalse(second["ok"])
        self.assertEqual(second["command"], "pipeline.start")
        self.assertEqual(second["severity"], "warning")
        self.assertIn("still running from this bundle", second["message"])
        self.assertEqual(len(start_calls), 1)

    def test_pipeline_start_blocked_by_active_work_does_not_cancel_existing_schedule_watcher(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            watcher = facade._schedule_stop_watcher  # type: ignore[attr-defined]
            watcher.arm(
                service=service,
                resolved=resolved,
                proc=DummyProc(24681),
                deadline=datetime.now() + timedelta(seconds=30),
            )
            service.find_related_pipeline_processes = lambda _resolved_arg: [DummyProc(24681)]  # type: ignore[method-assign]

            blocked = facade.start_pipeline_process(resolved, {"mode": "validate"}).to_mapping()
            state = watcher.state()
            watcher.cancel("test cleanup")

        self.assertFalse(blocked["ok"])
        self.assertEqual(state.status, "armed")
        self.assertEqual(state.pid, 24681)

    def test_launch_preflight_is_read_only_and_matches_launch_guards(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            csv_path = root / "rerun.csv"
            csv_path.write_text("enabled,source_path\ntrue,C:\\Media\\Movie.mkv\n", encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data = {"Outsource": str(root / "Outsource")}

            pipeline = facade.get_launch_preflight(
                resolved,
                {"target": "pipeline", "mode": "validate", "sleep_seconds": 3},
            )
            invalid_mode = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "bad"})
            audit = facade.get_launch_preflight(resolved, {"target": "audit", "include_sidecars": True})
            rerun = facade.get_launch_preflight(resolved, {"target": "rerun", "csv_path": str(csv_path)})
            blocked_rerun = facade.get_launch_preflight(
                resolved,
                {"target": "rerun", "csv_path": str(csv_path), "original_mode": "delete"},
            )
            has_started_side_effects = any(
                hasattr(service, attr)
                for attr in ("started_pipeline", "started_audit", "started_rerun")
            )

        self.assertEqual(pipeline["schema_version"], "desktop_launch_preflight.v1")
        self.assertEqual(pipeline["target"], "pipeline")
        self.assertTrue(pipeline["can_request_start"])
        self.assertEqual(pipeline["start_route"], "/api/pipeline/start")
        self.assertEqual(pipeline["operator_readiness"]["schema_version"], "desktop_launch_readiness.v1")
        self.assertEqual(pipeline["operator_readiness"]["evidence_authority"], "backend")
        self.assertEqual(pipeline["operator_readiness"]["source_route"], "/api/launch/preflight")
        self.assertEqual(pipeline["operator_readiness"]["display_status"], "Review")
        self.assertIn("Launch readiness (backend-authored):", pipeline["operator_readiness"]["summary_lines"])
        self.assertTrue(any("Backend launch locking and gating remain the source of truth." in line for line in pipeline["operator_readiness"]["summary_lines"]))
        self.assertTrue(any(row["key"] == "runtime_prep_boundary" for row in pipeline["checks"]))
        self.assertFalse(has_started_side_effects)
        self.assertEqual(invalid_mode["status"], "blocked")
        self.assertFalse(invalid_mode["can_request_start"])
        self.assertEqual(invalid_mode["operator_readiness"]["display_status"], "Blocked")
        self.assertGreaterEqual(invalid_mode["operator_readiness"]["non_ready_count"], 1)
        self.assertTrue(any(row["key"] == "mode" and row["status"] == "blocked" for row in invalid_mode["checks"]))
        self.assertEqual(audit["target"], "audit")
        self.assertEqual(audit["start_route"], "/api/audit/start")
        self.assertEqual(audit["request"]["library_root"], str(root / "Outsource"))
        self.assertEqual(rerun["target"], "rerun")
        self.assertEqual(rerun["start_route"], "/api/rerun/start")
        self.assertEqual(rerun["request"]["stage_mode"], "copy")
        self.assertEqual(blocked_rerun["status"], "blocked")
        self.assertTrue(any(row["key"] == "safe_modes" and row["status"] == "blocked" for row in blocked_rerun["checks"]))

    def test_launch_preflight_reports_schedule_and_lock_blocks_without_launching(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            service.save_app_state({"schedule_enabled": True, "schedule_grid": service.default_schedule_grid()})
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            schedule_blocked = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "continuous"})
            self.assertTrue(facade._process_launch_lock.acquire(blocking=False))  # type: ignore[attr-defined]
            try:
                lock_blocked = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "validate"})
            finally:
                facade._process_launch_lock.release()  # type: ignore[attr-defined]

        self.assertEqual(schedule_blocked["status"], "blocked")
        self.assertFalse(schedule_blocked["can_request_start"])
        self.assertTrue(any(row["key"] == "schedule_gate" and row["status"] == "blocked" for row in schedule_blocked["checks"]))
        self.assertTrue(any("outside the allowed schedule" in " ".join(str(item) for item in row["detail"]) for row in schedule_blocked["checks"] if row["key"] == "schedule_gate"))
        self.assertEqual(lock_blocked["status"], "blocked")
        self.assertFalse(lock_blocked["can_request_start"])
        self.assertTrue(any(row["key"] == "process_launch_lock" and row["status"] == "blocked" for row in lock_blocked["checks"]))
        self.assertFalse(hasattr(service, "started_pipeline"))

    def test_launch_preflight_reports_continuous_schedule_stop_watcher_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            service.save_app_state({"schedule_enabled": True, "schedule_grid": service.default_schedule_grid()})
            service.evaluate_schedule = lambda _enabled, _grid: {  # type: ignore[method-assign]
                "enabled": True,
                "allowed_now": True,
                "status_text": "Schedule: Allowed now until Thursday 11:30 PM",
                "current_window_end": "2026-05-14T23:30:00",
                "next_allowed_start": "2026-05-14T22:00:00",
                "next_allowed_end": "2026-05-14T23:30:00",
                "next_transition": "2026-05-14T23:30:00",
            }
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            preflight = facade.get_launch_preflight(resolved, {"target": "pipeline", "mode": "continuous"})
            ignored = facade.get_launch_preflight(
                resolved,
                {"target": "pipeline", "mode": "continuous", "schedule_override": "ignore"},
            )

        watcher_rows = [row for row in preflight["checks"] if row["key"] == "continuous_schedule_stop_watcher"]
        ignored_watcher = [row for row in ignored["checks"] if row["key"] == "continuous_schedule_stop_watcher"]
        self.assertNotEqual(preflight["status"], "blocked")
        self.assertTrue(preflight["can_request_start"])
        self.assertEqual(len(watcher_rows), 1)
        self.assertEqual(watcher_rows[0]["status"], "ready")
        self.assertIn("backend watcher available", watcher_rows[0]["evidence"])
        self.assertIn("2026-05-14T23:30:00", watcher_rows[0]["evidence"])
        self.assertEqual(ignored["status"], "high review")
        self.assertTrue(ignored["can_request_start"])
        self.assertEqual(ignored_watcher[0]["status"], "high review")
        self.assertIn("Ignore Schedule", ignored_watcher[0]["action"])
