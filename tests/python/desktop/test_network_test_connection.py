from __future__ import annotations

import sys
import tempfile
import unittest
import json
from pathlib import Path
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.application.facade import MediaPipelineApplicationFacade
from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.desktop.network.probe import NetworkProbeResult


class _TcpConnectOk:
    def __enter__(self) -> "_TcpConnectOk":
        return self

    def __exit__(self, *_args: object) -> bool:
        return False


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
        config_data=config,
    )


def _worker_config(source_movies: Path, source_tv: Path, output: Path) -> dict[str, object]:
    return {
        "NetworkRole": "worker",
        "WorkerCoordinatorUrl": "http://coordinator.test:7830",
        "WorkerAuthToken": "secret-token",
        "SourceMovies": str(source_movies),
        "SourceTV": str(source_tv),
        "Outsource": str(output),
    }


def _get_json(url: str, token: str) -> tuple[int, dict]:
    from urllib.error import HTTPError
    from urllib.request import Request, urlopen

    request = Request(url, headers={"Authorization": f"Bearer {token}"})
    try:
        with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
            return response.status, json.loads(response.read().decode("utf-8"))
    except HTTPError as exc:
        return exc.code, json.loads(exc.read().decode("utf-8"))


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


class NetworkWorkerTestConnectionTests(unittest.TestCase):
    def test_worker_test_connection_reports_all_layers_pass_without_exposing_token(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_movies = root / "Movies"
            source_tv = root / "TV"
            output = root / "Output"
            for path in (source_movies, source_tv, output):
                path.mkdir(parents=True)
            resolved = _resolved(root, _worker_config(source_movies, source_tv, output))
            facade = MediaPipelineApplicationFacade(object(), app_version="v6-test")

            with (
                patch("mediapipeline.core.network.facade.socket.create_connection", return_value=_TcpConnectOk()) as tcp_connect,
                patch.object(
                    facade,
                    "_network_probe_worker_auth",
                    return_value=NetworkProbeResult(True, "Auth ping accepted (HTTP 200)", 200),
                ) as auth_ping,
            ):
                result = facade.request_network_test_connection(
                    resolved,
                    {"timeout_seconds": 2},
                ).to_mapping()

        self.assertTrue(result["ok"])
        self.assertEqual(result["severity"], "info")
        self.assertEqual(result["command"], "network.worker.test_connection")
        self.assertEqual(result["data"]["schema_version"], "desktop_network_worker_test_connection.v1")
        self.assertEqual(result["data"]["effect"], "none")
        self.assertEqual(result["data"]["dry_run_writes"], [])
        self.assertTrue(result["data"]["suppress_command_journal"])
        self.assertTrue(result["data"]["read_only"])
        self.assertEqual(result["data"]["overall_status"], "pass")
        self.assertEqual(result["data"]["coordinator_url"], "http://coordinator.test:7830")
        self.assertTrue(result["data"]["layers"]["l1_tcp"]["ok"])
        self.assertTrue(result["data"]["layers"]["l2_auth"]["ok"])
        self.assertTrue(result["data"]["layers"]["l3_paths"]["ok"])
        self.assertGreaterEqual(len(result["data"]["layers"]["l3_paths"]["paths"]), 3)
        self.assertIn("No files, queue, scratch, output", "\n".join(result["data"]["summary_lines"]))
        self.assertEqual(result["data"]["would_not_touch"]["queue_state"], "no claim, enqueue, dequeue, reorder, or launch")
        self.assertNotIn("secret-token", str(result))
        tcp_connect.assert_called_once_with(("coordinator.test", 7830), timeout=2.0)
        auth_ping.assert_called_once_with("http://coordinator.test:7830", "secret-token", timeout_seconds=2)

    def test_worker_test_connection_reports_auth_layer_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_movies = root / "Movies"
            source_tv = root / "TV"
            output = root / "Output"
            for path in (source_movies, source_tv, output):
                path.mkdir(parents=True)
            resolved = _resolved(root, _worker_config(source_movies, source_tv, output))
            facade = MediaPipelineApplicationFacade(object(), app_version="v6-test")

            with (
                patch("mediapipeline.core.network.facade.socket.create_connection", return_value=_TcpConnectOk()),
                patch.object(
                    facade,
                    "_network_probe_worker_auth",
                    return_value=NetworkProbeResult(False, "401 Unauthorized - token does not match coordinator", 401),
                ),
            ):
                result = facade.request_network_test_connection(resolved, {}).to_mapping()

        self.assertFalse(result["ok"])
        self.assertEqual(result["severity"], "error")
        self.assertTrue(result["data"]["layers"]["l1_tcp"]["ok"])
        self.assertFalse(result["data"]["layers"]["l2_auth"]["ok"])
        self.assertTrue(result["data"]["layers"]["l3_paths"]["ok"])
        self.assertIn("401 Unauthorized", result["errors"][0])

    def test_worker_test_connection_reports_path_layer_failure_as_warning(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_movies = root / "Movies"
            source_tv = root / "TV"
            output = root / "Output"
            source_movies.mkdir(parents=True)
            output.mkdir(parents=True)
            resolved = _resolved(root, _worker_config(source_movies, source_tv, output))
            facade = MediaPipelineApplicationFacade(object(), app_version="v6-test")

            with (
                patch("mediapipeline.core.network.facade.socket.create_connection", return_value=_TcpConnectOk()),
                patch.object(
                    facade,
                    "_network_probe_worker_auth",
                    return_value=NetworkProbeResult(True, "Auth ping accepted (HTTP 200)", 200),
                ),
            ):
                result = facade.request_network_test_connection(resolved, {}).to_mapping()

        self.assertFalse(result["ok"])
        self.assertEqual(result["severity"], "warning")
        self.assertTrue(result["data"]["layers"]["l1_tcp"]["ok"])
        self.assertTrue(result["data"]["layers"]["l2_auth"]["ok"])
        self.assertFalse(result["data"]["layers"]["l3_paths"]["ok"])
        failed_paths = [
            row
            for row in result["data"]["layers"]["l3_paths"]["paths"]
            if not row["ok"]
        ]
        self.assertEqual(len(failed_paths), 1)
        self.assertEqual(failed_paths[0]["path_kind"], "source_root")
        self.assertIn("not reachable", failed_paths[0]["detail"])

    def test_worker_test_connection_rejects_invalid_worker_url_without_tcp_connect(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            media = root / "Media"
            media.mkdir()
            resolved = _resolved(
                root,
                {
                    **_worker_config(media, media, media),
                    "WorkerCoordinatorUrl": "http://0.0.0.0:7830",
                },
            )
            facade = MediaPipelineApplicationFacade(object(), app_version="v6-test")

            with (
                patch("mediapipeline.core.network.facade.socket.create_connection") as tcp_connect,
                patch.object(facade, "_network_probe_worker_auth") as auth_ping,
            ):
                result = facade.request_network_test_connection(resolved, {}).to_mapping()

        self.assertFalse(result["ok"])
        self.assertEqual(result["severity"], "error")
        self.assertFalse(result["data"]["layers"]["l1_tcp"]["ok"])
        self.assertFalse(result["data"]["layers"]["l2_auth"]["ok"])
        self.assertIn("not a bind-all listen address", result["data"]["layers"]["l1_tcp"]["detail"])
        tcp_connect.assert_not_called()
        auth_ping.assert_not_called()

    def test_local_api_worker_test_connection_route_is_read_only_and_unjournaled(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_movies = root / "Movies"
            source_tv = root / "TV"
            output = root / "Output"
            for path in (source_movies, source_tv, output, root / "LocalBase" / "State"):
                path.mkdir(parents=True)
            resolved = _resolved(root, _worker_config(source_movies, source_tv, output))
            facade = MediaPipelineApplicationFacade(object(), app_version="v6-test")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                with (
                    patch(
                        "mediapipeline.core.network.facade._network_tcp_probe",
                        return_value={
                            "key": "l1_tcp",
                            "label": "L1 TCP coordinator reachability",
                            "status": "pass",
                            "ok": True,
                            "detail": "TCP connect succeeded for http://coordinator.test:7830.",
                            "coordinator_url": "http://coordinator.test:7830",
                            "host": "coordinator.test",
                            "port": 7830,
                        },
                    ),
                    patch(
                        "mediapipeline.core.network.facade._network_auth_ping_probe",
                        return_value={
                            "key": "l2_auth",
                            "label": "L2 signed coordinator auth ping",
                            "status": "pass",
                            "ok": True,
                            "detail": "Auth ping accepted (HTTP 200)",
                            "coordinator_url": "http://coordinator.test:7830",
                            "status_code": 200,
                        },
                    ),
                ):
                    status, payload = _post_json(
                        f"{server.url}/api/network/worker/test-connection",
                        {"timeout_seconds": 3},
                        "test-token",
                    )
                commands_status, commands = _get_json(f"{server.url}/api/commands?limit=10", "test-token")
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["schema_version"], "desktop_network_worker_test_connection.v1")
        self.assertEqual(payload["data"]["effect"], "none")
        self.assertTrue(payload["data"]["suppress_command_journal"])
        self.assertTrue(payload["data"]["layers"]["l1_tcp"]["ok"])
        self.assertTrue(payload["data"]["layers"]["l2_auth"]["ok"])
        self.assertTrue(payload["data"]["layers"]["l3_paths"]["ok"])
        self.assertEqual(commands_status, 200)
        self.assertEqual(commands["entries"], [])


if __name__ == "__main__":
    unittest.main()
