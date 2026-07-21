from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.core.processes.kill import RelatedProcessKillEvidence, RelatedProcessKillReport
from mediapipeline.core.status.run_monitor import RunMonitorStore
from tests.python.core.contract.test_run_monitor_contract import RUN_ID, _item, _payload, _worker
from tests.python.desktop.application_facade_test_support import DummyWorkflowFacadeService, _resolved


class ApplicationFacadeProcessControlTests(unittest.TestCase):
    @staticmethod
    def _write_active_pipeline_job(
        resolved,
        *,
        launch_id: str = "launch-123",
        pid: int = 24680,
        run_id: str = "run-once-123",
        command_id: str | None = None,
        mode: str = "once",
        single_file: str = "",
        queue_fingerprint: str = "accepted-queue-fingerprint",
    ) -> Path:
        assert resolved.active_jobs_path is not None
        resolved.active_jobs_path.mkdir(parents=True, exist_ok=True)
        target = resolved.active_jobs_path / f"{launch_id}.json"
        metadata = {
            "run_id": run_id,
            "mode": mode,
            "single_file": single_file,
            "expected_queue_plan_fingerprint": queue_fingerprint,
        }
        if command_id is not None:
            metadata["command_id"] = command_id
        target.write_text(
            json.dumps(
                {
                    "schema_version": "desktop_active_job.v1",
                    "launch_id": launch_id,
                    "job_kind": "pipeline",
                    "mode": mode,
                    "status": "active",
                    "pid": pid,
                    "metadata": metadata,
                }
            ),
            encoding="utf-8",
        )
        return target

    def test_pipeline_control_uses_existing_control_flag_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            pause = facade.request_pipeline_control(resolved, "pause").to_mapping()
            rescan = facade.request_pipeline_control(resolved, "rescan").to_mapping()
            service.kill_related_pipeline_processes = lambda _resolved: [  # type: ignore[method-assign]
                "Force-killed related MediaPipeline process tree (PID 1234)."
            ]
            kill = facade.request_pipeline_control(resolved, "kill", confirm_force_stop=True).to_mapping()
            invalid = facade.request_pipeline_control(resolved, "launch-everything").to_mapping()
            pause_payload = json.loads(resolved.pause_flag.read_text(encoding="utf-8"))  # type: ignore[union-attr]
            rescan_payload = json.loads(resolved.rescan_flag.read_text(encoding="utf-8"))  # type: ignore[union-attr]

        self.assertTrue(pause["ok"])
        self.assertEqual(pause["command"], "pipeline.control.pause")
        self.assertEqual(pause_payload["action"], "pause")
        self.assertTrue(rescan["ok"])
        self.assertEqual(rescan_payload["action"], "rescan")
        self.assertTrue(kill["ok"])
        self.assertEqual(kill["data"]["force_stop_scope"]["job_kinds"], ["pipeline", "audit", "rerun_csv"])
        self.assertIn("pipeline, audit, and CSV rerun", kill["data"]["force_stop_scope"]["scope_label"])
        self.assertEqual(kill["data"]["killed_process_tree_count"], 1)
        self.assertIn("PID 1234", kill["data"]["kill_report"][0])
        self.assertFalse(invalid["ok"])
        self.assertIn("pause, stop, rescan, or kill", invalid["errors"][0])

    def test_kill_resets_idle_progress_with_stale_blocking_status(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.progress_file = root / "State" / "Progress" / "pipeline_progress.json"
            resolved.progress_file.parent.mkdir(parents=True, exist_ok=True)
            resolved.progress_file.write_text(
                json.dumps(
                    {
                        "ProgressVersion": 2,
                        "LastUpdate": "2026-07-01 09:06:49",
                        "CurrentFile": "None",
                        "CurrentStage": "idle",
                        "Status": "Autonomy health blocked",
                    }
                ),
                encoding="utf-8",
            )
            service.kill_related_pipeline_processes = lambda _resolved: []  # type: ignore[method-assign]

            kill = facade.request_pipeline_control(resolved, "kill", confirm_force_stop=True).to_mapping()
            progress = json.loads(resolved.progress_file.read_text(encoding="utf-8"))

        self.assertTrue(kill["ok"])
        self.assertEqual(progress["CurrentStage"], "idle")
        self.assertEqual(progress["Status"], "Idle")
        self.assertIn("status='autonomy health blocked'", kill["data"]["progress_reset"])

    def test_force_stop_terminalizes_exact_active_run_monitor_aftermath(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.run_monitor_path = resolved.state_root / "RunMonitor"
            active_item = _item(1, 2, lifecycle_state="active", active_stage="transcode")
            active_item["output"].update(
                {
                    "state": "active",
                    "scratch_path": r"C:\Scratch\Movie-1.mkv",
                    "working_output_path": r"C:\Scratch\Movie-1.partial.mkv",
                    "verification_state": "not_started",
                }
            )
            queued_item = _item(2, 2, lifecycle_state="queued")
            store = RunMonitorStore(resolved.state_root)
            store.write(_payload([active_item, queued_item], workers=[_worker(1, str(active_item["job_id"]))]))
            self._write_active_pipeline_job(resolved, run_id=RUN_ID)
            service.kill_related_pipeline_processes = lambda _resolved: RelatedProcessKillReport(  # type: ignore[method-assign]
                ["Force-killed related MediaPipeline process tree (PID 24680)."],
                termination_evidence=[
                    RelatedProcessKillEvidence(
                        pid=24680,
                        matched_job_kinds=("pipeline",),
                        run_id=RUN_ID,
                        command_id="",
                        exit_verified=True,
                    )
                ],
            )

            kill = facade.request_pipeline_control(resolved, "kill", confirm_force_stop=True).to_mapping()
            aftermath = store.read(RUN_ID)

        self.assertTrue(kill["ok"])
        self.assertIsNotNone(aftermath)
        assert aftermath is not None
        self.assertEqual(aftermath.run.lifecycle_state, "force_stopped")
        self.assertEqual(aftermath.run.outcome.state, "force_stopped")
        self.assertEqual(aftermath.run.counts.stopped, 2)
        self.assertEqual([item.lifecycle_state for item in aftermath.items], ["stopped", "stopped"])
        self.assertEqual(aftermath.current_workers, [])
        transcode = aftermath.items[0].stage("transcode")
        self.assertEqual(transcode.state, "failed")
        self.assertEqual(transcode.reason_code, "force_stopped_by_operator")
        self.assertEqual(aftermath.items[0].failure.state, "force_stopped")
        self.assertEqual(aftermath.items[0].recovery.owner, "operator")
        self.assertEqual(aftermath.items[0].output.state, "failed")
        self.assertEqual(aftermath.items[0].output.working_output_path, r"C:\Scratch\Movie-1.partial.mkv")
        self.assertEqual(aftermath.items[0].output.evidence.source, "force_stop_control")
        self.assertIn(RUN_ID, kill["data"]["force_stopped_run_ids"])

    def test_force_stop_does_not_terminalize_active_run_when_no_process_was_killed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.run_monitor_path = resolved.state_root / "RunMonitor"
            active_item = _item(1, 1, lifecycle_state="active", active_stage="transcode")
            store = RunMonitorStore(resolved.state_root)
            store.write(_payload([active_item], workers=[_worker(1, str(active_item["job_id"]))]))
            self._write_active_pipeline_job(resolved, run_id=RUN_ID)
            service.kill_related_pipeline_processes = lambda _resolved: []  # type: ignore[method-assign]

            kill = facade.request_pipeline_control(resolved, "kill", confirm_force_stop=True).to_mapping()
            aftermath = store.read(RUN_ID)

        self.assertTrue(kill["ok"])
        self.assertIsNotNone(aftermath)
        assert aftermath is not None
        self.assertEqual(aftermath.run.lifecycle_state, "running")
        self.assertEqual(aftermath.items[0].lifecycle_state, "active")
        self.assertEqual(kill["data"]["force_stopped_run_ids"], [])

    def test_force_stop_does_not_terminalize_pipeline_run_for_unrelated_audit_or_rerun_kills(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.run_monitor_path = resolved.state_root / "RunMonitor"
            active_item = _item(1, 1, lifecycle_state="active", active_stage="transcode")
            store = RunMonitorStore(resolved.state_root)
            store.write(_payload([active_item], workers=[_worker(1, str(active_item["job_id"]))]))
            self._write_active_pipeline_job(resolved, run_id=RUN_ID)
            service.kill_related_pipeline_processes = lambda _resolved: RelatedProcessKillReport(  # type: ignore[method-assign]
                [
                    "Force-killed related MediaPipeline audit process tree (PID 24681).",
                    "Force-killed related MediaPipeline rerun_csv process tree (PID 24682).",
                ],
                termination_evidence=[
                    RelatedProcessKillEvidence(
                        pid=24681,
                        matched_job_kinds=("audit",),
                        run_id="",
                        command_id="",
                        exit_verified=True,
                    ),
                    RelatedProcessKillEvidence(
                        pid=24682,
                        matched_job_kinds=("rerun_csv",),
                        run_id="",
                        command_id="",
                        exit_verified=True,
                    ),
                ],
            )

            kill = facade.request_pipeline_control(resolved, "kill", confirm_force_stop=True).to_mapping()
            aftermath = store.read(RUN_ID)

        self.assertTrue(kill["ok"])
        self.assertIsNotNone(aftermath)
        assert aftermath is not None
        self.assertEqual(aftermath.run.lifecycle_state, "running")
        self.assertEqual(aftermath.items[0].lifecycle_state, "active")
        self.assertEqual(kill["data"]["force_stopped_run_ids"], [])

    def test_force_stop_rejects_kill_proof_for_same_pid_but_different_run(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.run_monitor_path = resolved.state_root / "RunMonitor"
            active_item = _item(1, 1, lifecycle_state="active", active_stage="transcode")
            store = RunMonitorStore(resolved.state_root)
            store.write(_payload([active_item], workers=[_worker(1, str(active_item["job_id"]))]))
            self._write_active_pipeline_job(resolved, run_id=RUN_ID)
            service.kill_related_pipeline_processes = lambda _resolved: RelatedProcessKillReport(  # type: ignore[method-assign]
                ["Force-killed related MediaPipeline process tree (PID 24680)."],
                termination_evidence=[
                    RelatedProcessKillEvidence(
                        pid=24680,
                        matched_job_kinds=("pipeline",),
                        run_id="different-run-id",
                        command_id="",
                        exit_verified=True,
                    )
                ],
            )

            kill = facade.request_pipeline_control(resolved, "kill", confirm_force_stop=True).to_mapping()
            aftermath = store.read(RUN_ID)

        self.assertTrue(kill["ok"])
        self.assertIsNotNone(aftermath)
        assert aftermath is not None
        self.assertEqual(aftermath.run.lifecycle_state, "running")
        self.assertEqual(kill["data"]["force_stopped_run_ids"], [])
        self.assertIn("no exact killed pipeline PID/RunId proof", kill["data"]["force_stop_monitor_errors"][0])

    def test_force_stop_requires_proof_for_every_active_pipeline_target_in_the_run(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.run_monitor_path = resolved.state_root / "RunMonitor"
            active_item = _item(1, 1, lifecycle_state="active", active_stage="transcode")
            store = RunMonitorStore(resolved.state_root)
            store.write(_payload([active_item], workers=[_worker(1, str(active_item["job_id"]))]))
            self._write_active_pipeline_job(resolved, launch_id="launch-a", pid=24680, run_id=RUN_ID)
            self._write_active_pipeline_job(resolved, launch_id="launch-b", pid=24681, run_id=RUN_ID)
            service.kill_related_pipeline_processes = lambda _resolved: RelatedProcessKillReport(  # type: ignore[method-assign]
                ["Force-killed related MediaPipeline process tree (PID 24680)."],
                termination_evidence=[
                    RelatedProcessKillEvidence(
                        pid=24680,
                        matched_job_kinds=("pipeline",),
                        run_id=RUN_ID,
                        command_id="",
                        exit_verified=True,
                    )
                ],
            )

            kill = facade.request_pipeline_control(resolved, "kill", confirm_force_stop=True).to_mapping()
            aftermath = store.read(RUN_ID)

        self.assertTrue(kill["ok"])
        self.assertIsNotNone(aftermath)
        assert aftermath is not None
        self.assertEqual(aftermath.run.lifecycle_state, "running")
        self.assertEqual(kill["data"]["force_stopped_run_ids"], [])
        self.assertIn("not every active pipeline target", kill["data"]["force_stop_monitor_errors"][0])

    def test_force_stop_requires_exact_command_id_when_active_job_records_one(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.run_monitor_path = resolved.state_root / "RunMonitor"
            active_item = _item(1, 1, lifecycle_state="active", active_stage="transcode")
            store = RunMonitorStore(resolved.state_root)
            store.write(_payload([active_item], workers=[_worker(1, str(active_item["job_id"]))]))
            self._write_active_pipeline_job(
                resolved,
                run_id=RUN_ID,
                command_id="expected-command-id",
            )
            service.kill_related_pipeline_processes = lambda _resolved: RelatedProcessKillReport(  # type: ignore[method-assign]
                ["Force-killed related MediaPipeline process tree (PID 24680)."],
                termination_evidence=[
                    RelatedProcessKillEvidence(
                        pid=24680,
                        matched_job_kinds=("pipeline",),
                        run_id=RUN_ID,
                        command_id="different-command-id",
                        exit_verified=True,
                    )
                ],
            )

            kill = facade.request_pipeline_control(resolved, "kill", confirm_force_stop=True).to_mapping()
            aftermath = store.read(RUN_ID)

        self.assertTrue(kill["ok"])
        self.assertIsNotNone(aftermath)
        assert aftermath is not None
        self.assertEqual(aftermath.run.lifecycle_state, "running")
        self.assertEqual(kill["data"]["force_stopped_run_ids"], [])

    def test_kill_requires_literal_backend_confirmation_before_service_call(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            calls: list[str] = []
            service.kill_related_pipeline_processes = lambda _resolved: calls.append("kill") or []  # type: ignore[method-assign]

            missing = facade.request_pipeline_control(resolved, "kill").to_mapping()
            false = facade.request_pipeline_control(resolved, "kill", confirm_force_stop=False).to_mapping()

        self.assertFalse(missing["ok"])
        self.assertFalse(false["ok"])
        self.assertEqual(calls, [])
        self.assertIn("confirm_force_stop=true", missing["errors"][0])

    def test_stop_writes_only_correlated_stop_after_current_marker(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            self._write_active_pipeline_job(resolved)

            stop = facade.request_pipeline_control(
                resolved,
                "stop",
                expected_run_id="run-once-123",
            ).to_mapping()
            marker = json.loads(resolved.stop_after_current_flag.read_text(encoding="utf-8"))

        self.assertTrue(stop["ok"])
        self.assertEqual(stop["command"], "pipeline.control.stop")
        self.assertEqual(stop["data"]["action"], "stop")
        self.assertEqual(stop["data"]["semantic_action"], "stop_after_current")
        self.assertEqual(stop["data"]["run_id"], "run-once-123")
        self.assertEqual(stop["data"]["target_pid"], 24680)
        self.assertEqual(stop["data"]["target_launch_id"], "launch-123")
        self.assertEqual(marker["action"], "stop_after_current")
        self.assertEqual(marker["run_id"], "run-once-123")
        self.assertEqual(marker["target_pid"], 24680)
        self.assertEqual(marker["target_launch_id"], "launch-123")
        self.assertFalse(resolved.stop_flag.exists())

    def test_stop_fails_honestly_without_one_exact_active_pipeline(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            absent = facade.request_pipeline_control(
                resolved,
                "stop",
                expected_run_id="run-a",
            ).to_mapping()
            self._write_active_pipeline_job(resolved, launch_id="launch-a", pid=1001, run_id="run-a")
            self._write_active_pipeline_job(resolved, launch_id="launch-b", pid=1002, run_id="run-b")
            ambiguous = facade.request_pipeline_control(
                resolved,
                "stop",
                expected_run_id="run-a",
            ).to_mapping()

        self.assertFalse(absent["ok"])
        self.assertIn("exactly one active pipeline", absent["message"])
        self.assertFalse(ambiguous["ok"])
        self.assertIn("exactly one active pipeline", ambiguous["message"])
        self.assertFalse(resolved.stop_after_current_flag.exists())

    def test_standard_backend_queue_stop_rejects_absent_stale_blank_or_wrong_scope_identity(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            active_path = self._write_active_pipeline_job(resolved, run_id="run-b")
            absent = facade.request_pipeline_control(resolved, "stop").to_mapping()
            stale_a = facade.request_pipeline_control(
                resolved,
                "stop",
                expected_run_id="run-a",
            ).to_mapping()
            self.assertFalse(resolved.stop_after_current_flag.exists())

            active_path.unlink()
            active_path = self._write_active_pipeline_job(resolved, run_id="")
            blank_backend_run = facade.request_pipeline_control(
                resolved,
                "stop",
                expected_run_id="run-b",
            ).to_mapping()
            self.assertFalse(resolved.stop_after_current_flag.exists())

            active_path.unlink()
            active_path = self._write_active_pipeline_job(
                resolved,
                mode="continuous",
                run_id="",
                queue_fingerprint="",
            )
            continuous = facade.request_pipeline_control(
                resolved,
                "stop",
                expected_run_id="run-b",
            ).to_mapping()
            self.assertFalse(resolved.stop_after_current_flag.exists())

            active_path.unlink()
            self._write_active_pipeline_job(
                resolved,
                run_id="",
                single_file=r"C:\Media\Single.mkv",
                queue_fingerprint="",
            )
            single_file = facade.request_pipeline_control(
                resolved,
                "stop",
                expected_run_id="run-b",
            ).to_mapping()

        for result in (absent, stale_a, blank_backend_run, continuous, single_file):
            self.assertFalse(result["ok"])
        self.assertIn("expected_run_id", absent["message"])
        self.assertIn("does not match", stale_a["message"])
        self.assertIn("nonblank run ID", blank_backend_run["message"])
        self.assertIn("Run Once", continuous["message"])
        self.assertIn("Backend Queue", single_file["message"])
        self.assertFalse(resolved.stop_after_current_flag.exists())

    def test_non_monitor_pipeline_stop_preserves_exact_process_correlation(self) -> None:
        cases = (
            ("continuous", "", ""),
            ("once", r"C:\Media\Single.mkv", ""),
        )
        for mode, single_file, queue_fingerprint in cases:
            with self.subTest(mode=mode, single_file=single_file), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root)
                service = DummyWorkflowFacadeService(root)
                facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
                resolved = _resolved(root)
                self._write_active_pipeline_job(
                    resolved,
                    mode=mode,
                    run_id="",
                    single_file=single_file,
                    queue_fingerprint=queue_fingerprint,
                )

                stop = facade.request_pipeline_control(resolved, "stop").to_mapping()
                marker = json.loads(resolved.stop_after_current_flag.read_text(encoding="utf-8"))

                self.assertTrue(stop["ok"])
                self.assertEqual(marker["run_id"], "")
                self.assertEqual(marker["target_pid"], 24680)
                self.assertEqual(marker["target_launch_id"], "launch-123")

    def test_pipeline_control_commands_share_backend_control_lock(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)

            self.assertTrue(facade._process_control_lock.acquire(blocking=False))  # type: ignore[attr-defined]
            try:
                pause = facade.request_pipeline_control(resolved, "pause").to_mapping()
                stop = facade.request_pipeline_control(resolved, "stop").to_mapping()
                rescan = facade.request_pipeline_control(resolved, "rescan").to_mapping()
            finally:
                facade._process_control_lock.release()  # type: ignore[attr-defined]
            pause_flag_exists = resolved.pause_flag.exists()  # type: ignore[union-attr]
            stop_flag_exists = resolved.stop_flag.exists()  # type: ignore[union-attr]
            rescan_flag_exists = resolved.rescan_flag.exists()  # type: ignore[union-attr]

        self.assertFalse(pause["ok"])
        self.assertFalse(stop["ok"])
        self.assertFalse(rescan["ok"])
        self.assertEqual(pause["severity"], "warning")
        self.assertIn("another pipeline control command is already in progress", pause["message"])
        self.assertIn("another pipeline control command is already in progress", stop["message"])
        self.assertIn("another pipeline control command is already in progress", rescan["message"])
        self.assertFalse(pause_flag_exists)
        self.assertFalse(stop_flag_exists)
        self.assertFalse(rescan_flag_exists)
