from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.network.join import decode_network_join_blob, encode_network_join_blob
from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application.facade import MediaPipelineApplicationFacade
from mediapipeline.desktop.models import ResolvedPaths
from tests.python.desktop.test_application_facade import DummyFacadeService


def _resolved(root: Path, config: dict[str, object]) -> ResolvedPaths:
    return ResolvedPaths(
        app_root=root,
        workspace_root=root,
        pipeline_path=root / "pipeline.ps1",
        config_path=root / "config.psd1",
        audit_script_path=root / "audit.ps1",
        rerun_script_path=root / "rerun.ps1",
        powershell_host=str(root / "pwsh.exe"),
        local_base=root / "LocalBase",
        state_root=root / "LocalBase" / "State",
        app_state_path=root / "LocalBase" / "State" / "App" / "desktop_app_state.json",
        config_data=config,
    )


def _library_profile(library_id: str, source: Path | str, output: Path | str) -> dict[str, object]:
    return {
        "id": library_id,
        "name": library_id.title(),
        "designation": "movie",
        "enabled": True,
        "source_path": str(source),
        "output_path": str(output),
    }


def _post_json(url: str, payload: dict, token: str) -> tuple[int, dict]:
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


def _get_json(url: str, token: str) -> tuple[int, dict]:
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    request = Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


class NetworkJoinTests(unittest.TestCase):
    def test_coordinator_join_blob_generates_app_state_token_and_library_payload(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            service.app_state_path = root / "LocalBase" / "State" / "App" / "desktop_app_state.json"
            movies = root / "CoordinatorMovies"
            output = root / "CoordinatorOutput"
            config = {
                "NetworkRole": "coordinator",
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorPort": 7830,
                "LibraryProfiles": [_library_profile("movies", movies, output)],
            }
            resolved = _resolved(root, config)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")

            result = facade.request_network_coordinator_join_blob(
                resolved,
                {
                    "confirm_create": True,
                    "coordinator_url": "http://coordinator.test:7830",
                },
            ).to_mapping()
            decoded = decode_network_join_blob(result["data"]["join_blob"])
            saved_token = service.load_app_state().get("coordinator_auth_token")

        self.assertTrue(result["ok"])
        self.assertEqual(result["command"], "network.coordinator.join_blob")
        self.assertEqual(result["data"]["schema_version"], "desktop_network_join_blob_result.v1")
        self.assertEqual(result["data"]["effect"], "secret-transfer")
        self.assertTrue(result["data"]["suppress_command_journal"])
        self.assertTrue(result["data"]["writes_app_state"])
        self.assertEqual(result["data"]["token_source"], "generated_app_state")
        self.assertEqual(result["data"]["library_count"], 1)
        self.assertEqual(decoded["coordinator_url"], "http://coordinator.test:7830")
        self.assertEqual(decoded["libraries"][0]["library_id"], "movies")
        self.assertEqual(saved_token, decoded["token"])
        self.assertNotIn(decoded["token"], json.dumps(result, sort_keys=True))

    def test_worker_join_import_saves_settings_seeds_path_map_and_runs_test(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "WorkerMovies"
            output = root / "WorkerOutput"
            for path in (source, output, root / "LocalBase" / "State" / "App"):
                path.mkdir(parents=True)
            config_path = root / "config.psd1"
            config_path.write_text("@{ NetworkRole = 'standalone' }\n", encoding="utf-8")
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            token = "join-token-0123456789"
            join_blob, _payload = encode_network_join_blob(
                coordinator_url="http://coordinator.test:7830",
                token=token,
                libraries=[
                    {
                        "library_id": "movies",
                        "name": "Movies",
                        "designation": "movie",
                        "source_root": r"C:\Coordinator\Movies",
                        "output_root": r"D:\Coordinator\Output",
                    }
                ],
                created_at_utc="2026-06-14T00:00:00Z",
            )
            resolved = _resolved(
                root,
                {
                    "NetworkRole": "standalone",
                    "SourceMovies": str(source),
                    "Outsource": str(output),
                    "LibraryProfiles": [_library_profile("movies", source, output)],
                },
            )
            resolved.config_path = config_path

            with (
                patch(
                    "mediapipeline.core.network.facade._network_tcp_probe",
                    return_value={
                        "key": "l1_tcp",
                        "label": "L1 TCP coordinator reachability",
                        "status": "pass",
                        "ok": True,
                        "detail": "TCP connect succeeded.",
                    },
                ),
                patch(
                    "mediapipeline.core.network.facade._network_auth_ping_probe",
                    return_value={
                        "key": "l2_auth",
                        "label": "L2 signed coordinator auth ping",
                        "status": "pass",
                        "ok": True,
                        "detail": "Auth ping accepted.",
                    },
                ),
            ):
                result = facade.request_network_worker_join_cluster(
                    resolved,
                    {
                        "join_blob": join_blob,
                        "confirm_import": True,
                        "timeout_seconds": 2,
                    },
                ).to_mapping()

        self.assertTrue(result["ok"])
        self.assertEqual(result["command"], "network.worker.join_cluster")
        self.assertEqual(result["data"]["schema_version"], "desktop_network_join_import_result.v1")
        self.assertTrue(result["data"]["suppress_command_journal"])
        self.assertEqual(result["data"]["settings_save"]["status"], "saved")
        self.assertTrue(result["data"]["test_connection"]["ok"])
        saved = service.saved_config_calls[-1]["config_values"]
        self.assertEqual(saved["NetworkRole"], "worker")
        self.assertEqual(saved["WorkerCoordinatorUrl"], "http://coordinator.test:7830")
        self.assertEqual(saved["WorkerAuthToken"], token)
        seeded_map = json.loads(saved["WorkerSourcePathMap"])
        self.assertEqual(seeded_map[r"C:\Coordinator\Movies"], str(source))
        self.assertEqual(result["data"]["join_plan"]["auto_path_map_entries"], 1)
        self.assertNotIn(token, json.dumps(result, sort_keys=True))

    def test_worker_join_import_requires_confirmation_without_saving(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root, {"NetworkRole": "standalone"})

            result = facade.request_network_worker_join_cluster(
                resolved,
                {"join_blob": "ignored"},
            ).to_mapping()

        self.assertFalse(result["ok"])
        self.assertEqual(result["severity"], "warning")
        self.assertTrue(result["data"]["suppress_command_journal"])
        self.assertEqual(service.saved_config_calls, [])

    def test_local_api_join_routes_are_unjournaled(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "WorkerMovies"
            output = root / "WorkerOutput"
            for path in (source, output, root / "LocalBase" / "State" / "App"):
                path.mkdir(parents=True)
            config_path = root / "config.psd1"
            config_path.write_text("@{ NetworkRole = 'standalone' }\n", encoding="utf-8")
            service = DummyFacadeService(root)
            service.app_state_path = root / "LocalBase" / "State" / "App" / "desktop_app_state.json"
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            coordinator_resolved = _resolved(
                root,
                {
                    "NetworkRole": "coordinator",
                    "CoordinatorBindAddress": "127.0.0.1",
                    "CoordinatorPort": 7830,
                    "LibraryProfiles": [_library_profile("movies", r"C:\Coordinator\Movies", r"D:\Coordinator\Output")],
                },
            )
            worker_resolved = _resolved(
                root,
                {
                    "NetworkRole": "standalone",
                    "SourceMovies": str(source),
                    "Outsource": str(output),
                    "LibraryProfiles": [_library_profile("movies", source, output)],
                },
            )
            worker_resolved.config_path = config_path
            resolved_holder = [coordinator_resolved]
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved_holder[0],
            )
            try:
                server.start()
                join_status, join_payload = _post_json(
                    f"{server.url}/api/network/coordinator/join-blob",
                    {
                        "confirm_create": True,
                        "coordinator_url": "http://coordinator.test:7830",
                    },
                    "test-token",
                )
                resolved_holder[0] = worker_resolved
                with (
                    patch(
                        "mediapipeline.core.network.facade._network_tcp_probe",
                        return_value={"key": "l1_tcp", "label": "L1", "status": "pass", "ok": True, "detail": "ok"},
                    ),
                    patch(
                        "mediapipeline.core.network.facade._network_auth_ping_probe",
                        return_value={"key": "l2_auth", "label": "L2", "status": "pass", "ok": True, "detail": "ok"},
                    ),
                ):
                    import_status, import_payload = _post_json(
                        f"{server.url}/api/network/worker/join-cluster",
                        {
                            "join_blob": join_payload["data"]["join_blob"],
                            "confirm_import": True,
                            "timeout_seconds": 2,
                        },
                        "test-token",
                    )
                commands_status, commands = _get_json(f"{server.url}/api/commands?limit=10", "test-token")
            finally:
                server.stop()

        self.assertEqual(join_status, 200)
        self.assertEqual(import_status, 200)
        self.assertTrue(join_payload["ok"])
        self.assertTrue(import_payload["ok"])
        self.assertEqual(commands_status, 200)
        self.assertEqual(commands["entries"], [])


if __name__ == "__main__":
    unittest.main()
