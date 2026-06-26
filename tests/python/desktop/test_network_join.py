from __future__ import annotations

import base64
import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.network import join as join_helpers
from mediapipeline.core.network.join import decode_network_join_blob, encode_network_join_blob
from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application.facade import MediaPipelineApplicationFacade
from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.desktop.network.path_map import apply_source_path_map, parse_source_path_map
from tests.python.desktop.application_facade_test_support import DummyFacadeService


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


def _join_blob_from_payload(payload: dict[str, object]) -> str:
    material = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
    return base64.urlsafe_b64encode(material).decode("ascii").rstrip("=")


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
    def test_decode_join_blob_rejects_malformed_schema_and_short_token_without_leaking_secret(self) -> None:
        with self.assertRaisesRegex(ValueError, "base64url encoded JSON object"):
            decode_network_join_blob("not a blob!!!")

        wrong_schema = _join_blob_from_payload(
            {
                "schema_version": "wrong.v1",
                "coordinator_url": "http://coordinator.test:7830",
                "token": "secret-token-0123456789",
                "libraries": [],
            }
        )
        with self.assertRaisesRegex(ValueError, "schema_version"):
            decode_network_join_blob(wrong_schema)

        short_secret = "short-secret"
        short_token = _join_blob_from_payload(
            {
                "schema_version": "desktop_network_join_blob.v1",
                "coordinator_url": "http://coordinator.test:7830",
                "token": short_secret,
                "libraries": [],
            }
        )
        with self.assertRaises(ValueError) as exc_info:
            decode_network_join_blob(short_token)
        self.assertIn("too short", str(exc_info.exception))
        self.assertNotIn(short_secret, str(exc_info.exception))

    def test_join_blob_caps_encoded_decoded_rows_and_field_lengths(self) -> None:
        with self.assertRaisesRegex(ValueError, "encoded payload is too large"):
            decode_network_join_blob("A" * (join_helpers.NETWORK_JOIN_BLOB_MAX_ENCODED_CHARS + 1))

        oversized_decoded = _join_blob_from_payload(
            {
                "schema_version": "desktop_network_join_blob.v1",
                "coordinator_url": "http://coordinator.test:7830",
                "token": "secret-token-0123456789",
                "padding": "x" * join_helpers.NETWORK_JOIN_BLOB_MAX_DECODED_BYTES,
                "libraries": [],
            }
        )
        with self.assertRaisesRegex(ValueError, "decoded payload is too large"):
            decode_network_join_blob(oversized_decoded)

        too_many_rows = _join_blob_from_payload(
            {
                "schema_version": "desktop_network_join_blob.v1",
                "coordinator_url": "http://coordinator.test:7830",
                "token": "secret-token-0123456789",
                "libraries": [
                    {"library_id": f"lib{i}", "source_root": f"C:/Media/{i}"}
                    for i in range(join_helpers.NETWORK_JOIN_BLOB_MAX_LIBRARY_ROWS + 1)
                ],
            }
        )
        with self.assertRaisesRegex(ValueError, "too many rows"):
            decode_network_join_blob(too_many_rows)

        long_field_secret = "s" * (join_helpers.NETWORK_JOIN_BLOB_MAX_SHORT_FIELD_CHARS + 1)
        long_field = _join_blob_from_payload(
            {
                "schema_version": "desktop_network_join_blob.v1",
                "coordinator_url": "http://coordinator.test:7830",
                "token": "secret-token-0123456789",
                "libraries": [{"library_id": long_field_secret, "source_root": "C:/Media"}],
            }
        )
        with self.assertRaises(ValueError) as exc_info:
            decode_network_join_blob(long_field)
        self.assertIn("field libraries[0].library_id is too long", str(exc_info.exception))
        self.assertNotIn(long_field_secret, str(exc_info.exception))

    def test_worker_join_import_rejects_hostile_blob_without_partial_save(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root, {"NetworkRole": "standalone"})
            hostile_secret = "short-secret"
            hostile_blob = _join_blob_from_payload(
                {
                    "schema_version": "desktop_network_join_blob.v1",
                    "coordinator_url": "http://coordinator.test:7830",
                    "token": hostile_secret,
                    "libraries": [],
                }
            )

            result = facade.request_network_worker_join_cluster(
                resolved,
                {
                    "join_blob": hostile_blob,
                    "confirm_import": True,
                    "timeout_seconds": 2,
                },
            ).to_mapping()

        self.assertFalse(result["ok"])
        self.assertEqual(service.saved_config_calls, [])
        self.assertNotIn(hostile_secret, json.dumps(result, sort_keys=True))
        self.assertNotIn(hostile_blob, json.dumps(result, sort_keys=True))

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

    def test_worker_join_preserves_manual_path_map_order_for_overlapping_prefixes(self) -> None:
        token = "join-token-0123456789"
        join_blob, _payload = encode_network_join_blob(
            coordinator_url="http://coordinator.test:7830",
            token=token,
            libraries=[],
            created_at_utc="2026-06-15T00:00:00Z",
        )
        manual_map = json.dumps(
            {
                r"C:\Coordinator\Movies\Special": r"D:\Special",
                r"C:\Coordinator\Movies": r"E:\Movies",
            }
        )

        _payload, changes, evidence = join_helpers.worker_join_patch_from_blob(
            join_blob,
            {"WorkerSourcePathMap": manual_map},
        )

        mappings = parse_source_path_map(changes["WorkerSourcePathMap"])
        self.assertEqual(
            mappings,
            [
                (r"C:\Coordinator\Movies\Special", r"D:\Special"),
                (r"C:\Coordinator\Movies", r"E:\Movies"),
            ],
        )
        self.assertEqual(
            apply_source_path_map(r"C:\Coordinator\Movies\Special\Film.mkv", mappings),
            r"D:\Special\Film.mkv",
        )
        self.assertEqual(evidence["manual_path_map_entries"], 2)
        self.assertEqual(evidence["effective_path_map_entries"], 2)

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

    def test_local_api_invalid_join_cluster_payload_does_not_journal_blob_or_token(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root, {"NetworkRole": "standalone"})
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
            )
            join_token = "join-token-0123456789"
            join_blob, _payload = encode_network_join_blob(
                coordinator_url="http://coordinator.test:7830",
                token=join_token,
                libraries=[],
                created_at_utc="2026-06-15T00:00:00Z",
            )
            try:
                server.start()
                import_status, import_payload = _post_json(
                    f"{server.url}/api/network/worker/join-cluster",
                    {
                        "join_blob": join_blob,
                        "confirm_import": True,
                        "timeout_seconds": 2,
                        "unknown_field": "reject-me",
                    },
                    "test-token",
                )
                commands_status, commands = _get_json(f"{server.url}/api/commands?limit=10", "test-token")
            finally:
                server.stop()

        self.assertEqual(import_status, 400)
        self.assertEqual(commands_status, 200)
        self.assertEqual(commands["entries"], [])
        combined = json.dumps({"import": import_payload, "commands": commands}, sort_keys=True)
        self.assertNotIn(join_blob, combined)
        self.assertNotIn(join_token, combined)


if __name__ == "__main__":
    unittest.main()
