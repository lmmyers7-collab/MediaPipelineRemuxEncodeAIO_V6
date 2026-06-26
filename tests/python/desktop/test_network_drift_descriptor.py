from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.network.path_map import parse_source_path_map
from mediapipeline.desktop.network.worker import WorkerDispatcher
from tests.python.desktop.application_facade_test_support import DummyFacadeService, _resolved


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:8]


def _worker(
    *,
    url: str,
    token: str,
    path_map: str,
    worker_encoder_map: str = "",
    honor_policy: bool = False,
) -> WorkerDispatcher:
    worker = WorkerDispatcher.__new__(WorkerDispatcher)
    worker._base_url = url
    worker._auth_token = token
    worker._source_path_map = parse_source_path_map(path_map)
    worker._worker_encoder_map = worker_encoder_map
    worker._worker_honor_coordinator_policy = honor_policy
    return worker


class NetworkWorkerDriftDescriptorTests(unittest.TestCase):
    def test_runtime_descriptor_reports_fingerprints_not_tokens(self) -> None:
        path_map = json.dumps({r"C:\Media": r"\\SERVER\Media"})
        worker_encoder_map = '{"hevc":"hevc_nvenc"}'
        worker = _worker(
            url="http://coordinator.test:7830",
            token="super-secret-token",
            path_map=path_map,
            worker_encoder_map=worker_encoder_map,
            honor_policy=True,
        )

        descriptor = worker.runtime_descriptor()

        self.assertEqual(descriptor["schema_version"], "desktop_network_worker_runtime_descriptor.v1")
        self.assertEqual(descriptor["coordinator_url"], "http://coordinator.test:7830")
        self.assertEqual(descriptor["token_fingerprint"], _fingerprint("super-secret-token"))
        self.assertEqual(descriptor["path_map_entries"], 1)
        self.assertEqual(len(descriptor["path_map_fingerprint"]), 8)
        self.assertIs(descriptor["honor_coordinator_policy"], True)
        self.assertEqual(descriptor["worker_encoder_map_entries"], 1)
        self.assertEqual(len(descriptor["worker_encoder_map_fingerprint"]), 8)
        self.assertNotIn("super-secret-token", json.dumps(descriptor))
        self.assertNotIn("hevc_nvenc", json.dumps(descriptor))

    def test_network_workers_reports_matching_running_worker_settings(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            resolved = _resolved(root)
            path_map = json.dumps({r"C:\Media": r"\\SERVER\Media"})
            resolved.config_data.update(
                {
                    "NetworkRole": "worker",
                    "WorkerCoordinatorUrl": "http://coordinator.test:7830/",
                    "WorkerAuthToken": "shared-token",
                    "WorkerSourcePathMap": path_map,
                }
            )
            facade._network_lifecycle_state_commit("worker", {"role": "worker", "status": "running"})
            facade._network_dispatcher_runtime = {
                "worker": {
                    "dispatcher": _worker(
                        url="http://coordinator.test:7830",
                        token="shared-token",
                        path_map=path_map,
                    )
                }
            }

            payload = facade.get_network_workers(resolved).to_mapping()

        drift = payload["running_vs_saved"]
        self.assertEqual(drift["status"], "match")
        self.assertEqual(drift["drift_fields"], [])
        self.assertEqual(drift["policy_divergence"]["status"], "review")
        self.assertEqual(drift["policy_divergence"]["fields"], ["coordinator_policy_disabled"])
        self.assertEqual(payload["runtime_status_label"], "Running")
        self.assertEqual(payload["runtime_status_severity"], "match")
        self.assertIn("Worker settings drift: none.", "\n".join(payload["operator_summary_lines"]))

    def test_network_workers_does_not_report_auto_library_path_map_as_saved_drift(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_data.update(
                {
                    "NetworkRole": "worker",
                    "WorkerCoordinatorUrl": "http://coordinator.test:7830/",
                    "WorkerAuthToken": "shared-token",
                    "WorkerSourcePathMap": "",
                }
            )
            worker = _worker(
                url="http://coordinator.test:7830",
                token="shared-token",
                path_map=json.dumps({r"C:\Coordinator\Movies": r"D:\WorkerMovies"}),
            )
            worker._manual_source_path_map = []
            worker._auto_source_path_map = parse_source_path_map(
                json.dumps({r"C:\Coordinator\Movies": r"D:\WorkerMovies"})
            )
            worker._source_path_map = list(worker._auto_source_path_map)
            facade._network_lifecycle_state_commit("worker", {"role": "worker", "status": "running"})
            facade._network_dispatcher_runtime = {"worker": {"dispatcher": worker}}

            payload = facade.get_network_workers(resolved).to_mapping()

        drift = payload["running_vs_saved"]
        self.assertEqual(drift["status"], "match")
        self.assertEqual(drift["source_path_map_status"], "auto-map-active")
        self.assertEqual(drift["drift_fields"], [])
        self.assertEqual(drift["saved"]["manual_path_map_entries"], 0)
        self.assertEqual(drift["running"]["manual_path_map_entries"], 0)
        self.assertEqual(drift["running"]["auto_path_map_entries"], 1)
        self.assertIn(
            "Worker settings drift: none (auto-derived library path map active).",
            "\n".join(payload["operator_summary_lines"]),
        )

    def test_network_workers_names_running_saved_drift_without_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_data.update(
                {
                    "NetworkRole": "worker",
                    "WorkerCoordinatorUrl": "http://saved-coordinator.test:7830",
                    "WorkerAuthToken": "saved-token",
                    "WorkerSourcePathMap": json.dumps({r"C:\Media": r"\\SAVED\Media"}),
                }
            )
            facade._network_lifecycle_state_commit("worker", {"role": "worker", "status": "running"})
            facade._network_dispatcher_runtime = {
                "worker": {
                    "dispatcher": _worker(
                        url="http://running-coordinator.test:7830",
                        token="running-token",
                        path_map=json.dumps({r"C:\Media": r"\\RUNNING\Media"}),
                    )
                }
            }

            payload = facade.get_network_workers(resolved).to_mapping()

        drift = payload["running_vs_saved"]
        self.assertEqual(drift["status"], "drift")
        self.assertEqual(
            drift["drift_fields"],
            ["coordinator_url", "worker_auth_token", "source_path_map"],
        )
        self.assertEqual(payload["runtime_status_label"], "Running with drift")
        self.assertEqual(payload["runtime_status_severity"], "warning")
        summary = "\n".join(payload["operator_summary_lines"])
        self.assertIn("Coordinator URL", summary)
        self.assertIn("Worker auth token fingerprint", summary)
        self.assertIn("Worker source path map", summary)
        self.assertIn("Worker running settings differ from saved config", "\n".join(payload["warnings"]))
        serialized = json.dumps(payload)
        self.assertNotIn("saved-token", serialized)
        self.assertNotIn("running-token", serialized)

    def test_network_workers_names_policy_runtime_drift_without_raw_map(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            resolved = _resolved(root)
            path_map = json.dumps({r"C:\Media": r"\\SERVER\Media"})
            resolved.config_data.update(
                {
                    "NetworkRole": "worker",
                    "WorkerCoordinatorUrl": "http://coordinator.test:7830",
                    "WorkerAuthToken": "shared-token",
                    "WorkerSourcePathMap": path_map,
                    "WorkerHonorCoordinatorPolicy": True,
                    "WorkerEncoderMap": '{"hevc":"hevc_nvenc"}',
                }
            )
            facade._network_lifecycle_state_commit("worker", {"role": "worker", "status": "running"})
            facade._network_dispatcher_runtime = {
                "worker": {
                    "dispatcher": _worker(
                        url="http://coordinator.test:7830",
                        token="shared-token",
                        path_map=path_map,
                        worker_encoder_map='{"hevc":"libx265"}',
                        honor_policy=False,
                    )
                }
            }

            payload = facade.get_network_workers(resolved).to_mapping()

        drift = payload["running_vs_saved"]
        self.assertEqual(drift["status"], "drift")
        self.assertEqual(drift["drift_fields"], ["coordinator_policy_flag", "worker_encoder_map"])
        self.assertEqual(drift["policy_divergence"]["status"], "ready")
        summary = "\n".join(payload["operator_summary_lines"])
        self.assertIn("Worker coordinator-policy flag", summary)
        self.assertIn("Worker encoder map", summary)
        serialized = json.dumps(payload)
        self.assertNotIn("hevc_nvenc", serialized)
        self.assertNotIn("libx265", serialized)

    def test_network_workers_reports_policy_review_when_flag_disabled(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            resolved = _resolved(root)
            path_map = json.dumps({r"C:\Media": r"\\SERVER\Media"})
            resolved.config_data.update(
                {
                    "NetworkRole": "worker",
                    "WorkerCoordinatorUrl": "http://coordinator.test:7830",
                    "WorkerAuthToken": "shared-token",
                    "WorkerSourcePathMap": path_map,
                    "WorkerHonorCoordinatorPolicy": False,
                    "WorkerEncoderMap": "",
                }
            )
            facade._network_lifecycle_state_commit("worker", {"role": "worker", "status": "running"})
            facade._network_dispatcher_runtime = {
                "worker": {
                    "dispatcher": _worker(
                        url="http://coordinator.test:7830",
                        token="shared-token",
                        path_map=path_map,
                        honor_policy=False,
                    )
                }
            }

            payload = facade.get_network_workers(resolved).to_mapping()

        drift = payload["running_vs_saved"]
        self.assertEqual(drift["status"], "match")
        self.assertEqual(drift["policy_divergence"]["status"], "review")
        self.assertEqual(drift["policy_divergence"]["fields"], ["coordinator_policy_disabled"])


if __name__ == "__main__":
    unittest.main()
