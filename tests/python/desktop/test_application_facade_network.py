from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from tests.python.desktop.application_facade_test_support import DummyFacadeService, _resolved


class ApplicationFacadeNetworkTests(unittest.TestCase):
    def test_network_workers_reads_persisted_runtime_state_without_lifecycle_control(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data["NetworkRole"] = "coordinator"
            resolved.config_data["CoordinatorBindAddress"] = "0.0.0.0"
            resolved.config_data["CoordinatorPort"] = 7830
            resolved.app_state_path = root / "State" / "App" / "desktop_app_state.json"
            state_dir = resolved.app_state_path.parent
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "coordinator_inflight.json").write_text(
                json.dumps(
                    {
                        "jobs": [
                            {
                                "job_id": "job-1",
                                "worker_id": "worker-1",
                                "worker_name": "Worker One",
                                "source_path": r"C:\Media\Show\S01E01.mkv",
                                "claimed_at": "2026-05-13T10:00:00+00:00",
                                "last_heartbeat": "2026-05-13T10:05:00+00:00",
                                "progress_percent": 42,
                                "current_stage": "encoding",
                                "encode_config": {},
                                "priority": True,
                                "estimated_size_gb": 2.5,
                            }
                        ],
                        "session_completed": 2,
                        "session_failed": 1,
                        "worker_stats": {
                            "worker-1": {"name": "Worker One", "files": 3, "gb": 6.5, "secs": 3600},
                            "idle-1": {"name": "Idle Worker", "files": 1, "gb": 2.0, "secs": 1800},
                        },
                    }
                ),
                encoding="utf-8",
            )
            (state_dir / "worker_state.json").write_text(
                json.dumps(
                    {
                        "job_id": "local-job",
                        "source_path": r"C:\Media\Movie.mkv",
                        "pending_done_report": {"success": True},
                    }
                ),
                encoding="utf-8",
            )
            (state_dir / "cluster.log").write_text(
                "\n".join(
                    [
                        "2026-05-13T10:01:00+00:00  INFO   worker/Worker One          claim_ok                  claimed job  job=job-1  src=S01E01.mkv",
                        "2026-05-13T10:02:00+00:00  INFO   worker/Worker One          encode_started            encoding started  job=job-1  src=S01E01.mkv",
                        "2026-05-13T10:03:00+00:00  ERROR  worker/Worker One          job_failed                SOURCE_NOT_FOUND  job=job-1  src=S01E01.mkv",
                    ]
                ),
                encoding="utf-8",
            )

            payload = facade.get_network_workers(resolved).to_mapping()

        self.assertEqual(payload["schema_version"], "desktop_network_workers.v1")
        self.assertEqual(payload["role"], "coordinator")
        self.assertEqual(payload["active_count"], 1)
        self.assertEqual(payload["idle_count"], 1)
        self.assertEqual(payload["session_completed"], 2)
        self.assertEqual(payload["session_failed"], 1)
        self.assertEqual(payload["worker_state"]["source_file"], "Movie.mkv")
        self.assertTrue(payload["worker_state"]["pending_done_report"])
        self.assertEqual(payload["rows"][0]["worker_name"], "Worker One")
        self.assertEqual(payload["rows"][0]["current_file_name"], "S01E01.mkv")
        self.assertIsInstance(payload["rows"][0]["heartbeat_age_seconds"], int)
        self.assertGreaterEqual(payload["rows"][0]["heartbeat_age_seconds"], 0)
        self.assertEqual(payload["worker_progress"]["schema_version"], "desktop_network_worker_progress.v1")
        connectivity = payload["coordinator_connectivity"]
        self.assertEqual(connectivity["schema_version"], "desktop_network_coordinator_connectivity.v1")
        self.assertEqual(connectivity["bind_endpoint"], "0.0.0.0:7830")
        self.assertTrue(connectivity["worker_coordinator_url"].startswith("http://"))
        self.assertNotIn("0.0.0.0", connectivity["worker_coordinator_url"])
        self.assertTrue(connectivity["candidate_urls"])
        self.assertIn("Worker coordinator URL:", "\n".join(connectivity["summary_lines"]))
        self.assertIn("heartbeat_age=", payload["progress_bars"][1]["detail"])
        self.assertTrue(any(bar["id"].startswith("network_worker_worker_1") for bar in payload["progress_bars"]))
        self.assertTrue(any(bar["id"] == "network_local_worker" and bar["status"] == "warning" for bar in payload["progress_bars"]))
        self.assertEqual(payload["lifecycle_state"]["schema_version"], "desktop_network_lifecycle_state.v1")
        self.assertEqual(payload["lifecycle_state"]["coordinator"]["status"], "stopped")
        self.assertEqual(payload["runtime_status_label"], "Blocked")
        self.assertEqual(payload["runtime_status_severity"], "blocked")
        self.assertIn("Normal Launch: blocked in this network mode", "\n".join(payload["operator_summary_lines"]))
        self.assertEqual(payload["token_posture"]["coordinator"]["status"], "blank")
        self.assertEqual(payload["token_posture"]["worker"]["status"], "missing")
        diagnostic = payload["diagnostic_layers"]
        self.assertEqual(diagnostic["schema_version"], "desktop_network_diagnostic_layers.v1")
        for key in ("url_reachable", "auth_ok", "paths_ok", "queue_fresh", "last_claim_result"):
            self.assertIn(key, diagnostic)
        self.assertTrue(any(layer["key"] == "last_claim_result" for layer in diagnostic["layers"]))
        self.assertNotIn("AuthToken", json.dumps(diagnostic))
        state_files = {item["key"]: item for item in payload["state_files"]}
        self.assertEqual(state_files["coordinator_inflight"]["status"], "present")
        self.assertEqual(state_files["worker_state"]["status"], "present")
        self.assertEqual(state_files["cluster_log"]["status"], "present")
        self.assertIn("Coordinator in-flight registry", state_files["coordinator_inflight"]["label"])
        self.assertTrue(state_files["coordinator_inflight"]["read_only"])
        self.assertIn("persisted in-flight state", "\n".join(payload["warnings"]))
        self.assertNotIn("attention_items", payload)
        self.assertNotIn("worker_event_timeline", payload)

    def test_network_workers_marks_malformed_coordinator_state_as_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_data["NetworkRole"] = "coordinator"
            resolved.app_state_path = root / "State" / "App" / "desktop_app_state.json"
            state_dir = resolved.app_state_path.parent
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "coordinator_inflight.json").write_text("{not valid json", encoding="utf-8")

            with self.assertLogs("mediapipeline.desktop.network.registry", level="ERROR") as logs:
                payload = facade.get_network_workers(resolved).to_mapping()

        state_files = {item["key"]: item for item in payload["state_files"]}
        self.assertIn("Failed to load InFlightRegistry", "\n".join(logs.output))
        self.assertEqual(payload["schema_version"], "desktop_network_workers.v1")
        self.assertEqual(payload["rows"], [])
        self.assertEqual(state_files["coordinator_inflight"]["status"], "unreadable")
        self.assertIn("coordinator_inflight.json", state_files["coordinator_inflight"]["error"])
        self.assertIn("Coordinator in-flight state could not be read", "\n".join(payload["warnings"]))
        self.assertEqual(payload["worker_progress"]["status"], "warning")

    def test_network_workers_marks_malformed_worker_state_row_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_data["NetworkRole"] = "worker"
            resolved.app_state_path = root / "State" / "App" / "desktop_app_state.json"
            state_dir = resolved.app_state_path.parent
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "worker_state.json").write_text("{not valid json", encoding="utf-8")

            payload = facade.get_network_workers(resolved).to_mapping()

        state_files = {item["key"]: item for item in payload["state_files"]}
        self.assertEqual(state_files["worker_state"]["status"], "unreadable")
        self.assertIn("worker_state", state_files["worker_state"]["error"])
        self.assertTrue(payload["worker_state"]["read_failed"])
        self.assertEqual(payload["runtime_status_label"], "Blocked")
        self.assertEqual(payload["runtime_status_severity"], "blocked")
        self.assertIn("Worker state could not be read", "\n".join(payload["warnings"]))

    def test_network_workers_warns_on_active_worker_state_with_stopped_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_data["NetworkRole"] = "worker"
            resolved.config_data["WorkerCoordinatorUrl"] = "http://coordinator.test:7830"
            resolved.config_data["WorkerAuthToken"] = "worker-token"
            resolved.app_state_path = root / "State" / "App" / "desktop_app_state.json"
            state_dir = resolved.app_state_path.parent
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "worker_state.json").write_text(
                json.dumps({"job_id": "stale-job", "source_path": r"C:\Media\Movie.mkv"}),
                encoding="utf-8",
            )

            payload = facade.get_network_workers(resolved).to_mapping()

        self.assertEqual(payload["worker_state"]["job_id"], "stale-job")
        self.assertEqual(payload["lifecycle_state"]["worker"]["status"], "stopped")
        self.assertEqual(payload["runtime_status_label"], "Stopped with stale worker claim")
        self.assertEqual(payload["runtime_status_severity"], "warning")
        warning_text = "\n".join(payload["warnings"])
        self.assertIn("stale claim evidence", warning_text)
        self.assertIn("Runtime: Stopped with stale worker claim (warning).", "\n".join(payload["operator_summary_lines"]))

    def test_network_workers_warns_when_coordinator_bind_is_loopback_only(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_data["NetworkRole"] = "coordinator"
            resolved.config_data["CoordinatorBindAddress"] = "127.0.0.1"
            resolved.config_data["CoordinatorPort"] = 9001

            payload = facade.get_network_workers(resolved).to_mapping()

        connectivity = payload["coordinator_connectivity"]
        self.assertEqual(connectivity["worker_coordinator_url"], "http://127.0.0.1:9001")
        self.assertEqual(connectivity["bind_endpoint"], "127.0.0.1:9001")
        self.assertIn("loopback", "\n".join(connectivity["warnings"]).lower())
        self.assertIn("workers on other machines cannot reach", "\n".join(payload["warnings"]).lower())

    def test_network_workers_treats_empty_worker_state_as_idle_not_warning(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_data["NetworkRole"] = "worker"
            resolved.app_state_path = root / "State" / "App" / "desktop_app_state.json"
            resolved.app_state_path.parent.mkdir(parents=True, exist_ok=True)
            (resolved.app_state_path.parent / "cluster.log").write_text("worker started\n", encoding="utf-8")

            payload = facade.get_network_workers(resolved).to_mapping()

        self.assertEqual(payload["role"], "worker")
        self.assertEqual(payload["worker_state"], {})
        self.assertEqual(payload["worker_progress"]["status"], "idle")
        self.assertEqual(payload["progress_bars"][0]["status"], "idle")
        self.assertEqual(payload["runtime_status_label"], "Stopped")
        self.assertEqual(payload["lifecycle_state"]["worker"]["status"], "stopped")
        self.assertIn("Worker token: missing", "\n".join(payload["operator_summary_lines"]))
        warning_text = "\n".join(payload["warnings"])
        self.assertNotIn("No coordinator in-flight state file exists yet", warning_text)
        self.assertNotIn("Worker runtime state is empty", warning_text)

    def test_network_workers_reports_session_lifecycle_state_without_starting_provider(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_data["NetworkRole"] = "worker"
            resolved.config_data["WorkerCoordinatorUrl"] = "http://coordinator.test:7830"
            resolved.config_data["WorkerAuthToken"] = "worker-token"
            facade._network_lifecycle_state_commit(
                "worker",
                {
                    "role": "worker",
                    "status": "running",
                    "last_command_id": "cmd-1",
                    "last_action": "start",
                    "state_scope": "session_memory_only",
                },
            )

            payload = facade.get_network_workers(resolved).to_mapping()

        self.assertEqual(payload["runtime_status_label"], "Running")
        self.assertEqual(payload["runtime_status_severity"], "match")
        self.assertEqual(payload["lifecycle_state"]["worker"]["status"], "running")
        self.assertEqual(payload["lifecycle_state"]["worker"]["last_command_id"], "cmd-1")
        self.assertEqual(payload["token_posture"]["worker"]["status"], "present")
        self.assertIn("Coordinator target: http://coordinator.test:7830.", "\n".join(payload["operator_summary_lines"]))
