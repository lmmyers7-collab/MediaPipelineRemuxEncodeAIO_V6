from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade
from DesktopApp.tests.test_application_facade import DummyFacadeService, _resolved


class ApplicationFacadeNetworkTests(unittest.TestCase):
    def test_network_workers_reads_persisted_runtime_state_without_lifecycle_control(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            resolved = _resolved(root)
            resolved.config_data["NetworkRole"] = "coordinator"
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
        self.assertIn("heartbeat_age=", payload["progress_bars"][1]["detail"])
        self.assertTrue(any(bar["id"].startswith("network_worker_worker_1") for bar in payload["progress_bars"]))
        self.assertTrue(any(bar["id"] == "network_local_worker" and bar["status"] == "warning" for bar in payload["progress_bars"]))
        state_files = {item["key"]: item for item in payload["state_files"]}
        self.assertEqual(state_files["coordinator_inflight"]["status"], "present")
        self.assertEqual(state_files["worker_state"]["status"], "present")
        self.assertEqual(state_files["cluster_log"]["status"], "missing")
        self.assertIn("Coordinator in-flight registry", state_files["coordinator_inflight"]["label"])
        self.assertTrue(state_files["coordinator_inflight"]["read_only"])
        self.assertIn("persisted in-flight state", "\n".join(payload["warnings"]))
