from __future__ import annotations

import base64
import json
import multiprocessing
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.network import join as join_helpers
from mediapipeline.core.network.join import decode_network_join_blob, encode_network_join_blob
from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.application.facade import MediaPipelineApplicationFacade
from mediapipeline.desktop.models import ResolvedPaths
from mediapipeline.desktop.network.coordinator import CoordinatorDispatcher
from mediapipeline.desktop.network.path_map import apply_source_path_map, parse_source_path_map
from tests.python.desktop.application_facade_test_support import DummyFacadeService


def _rotate_coordinator_token_process(root_text: str, token: str, result_queue) -> None:
    root = Path(root_text)
    service = DummyFacadeService(root)
    service.app_state_path = root / "desktop_app_state.json"
    dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
    dispatcher._auth_token = "existing-token-0123456789"
    dispatcher._app = SimpleNamespace(service=service)
    dispatcher._safe_log_cluster_event = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
    CoordinatorDispatcher.update_auth_token(dispatcher, token)
    result_queue.put(dispatcher._auth_token)


def _reload_coordinator_token_process(root_text: str, result_queue) -> None:
    root = Path(root_text)
    service = DummyFacadeService(root)
    service.app_state_path = root / "desktop_app_state.json"
    dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
    dispatcher._config = lambda: {}  # type: ignore[method-assign]
    dispatcher._app = SimpleNamespace(service=service)
    result_queue.put(CoordinatorDispatcher._load_or_generate_token(dispatcher))


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
    def test_rotated_token_survives_distinct_process_restart(self) -> None:
        context = multiprocessing.get_context("spawn")
        token = "restart-token-" + ("a" * 48)
        with tempfile.TemporaryDirectory() as raw_root:
            result_queue = context.Queue()
            rotating_process = None
            restarted_process = None
            try:
                rotating_process = context.Process(
                    target=_rotate_coordinator_token_process,
                    args=(raw_root, token, result_queue),
                )
                rotating_process.start()
                rotating_process.join(timeout=20)
                self.assertEqual(rotating_process.exitcode, 0)
                self.assertEqual(result_queue.get(timeout=5), token)

                restarted_process = context.Process(
                    target=_reload_coordinator_token_process,
                    args=(raw_root, result_queue),
                )
                restarted_process.start()
                restarted_process.join(timeout=20)
                self.assertEqual(restarted_process.exitcode, 0)
                self.assertEqual(result_queue.get(timeout=5), token)
            finally:
                for process in (rotating_process, restarted_process):
                    if process is not None and process.is_alive():
                        process.terminate()
                        process.join(timeout=5)
                result_queue.close()
                result_queue.join_thread()

            saved_state = json.loads((Path(raw_root) / "desktop_app_state.json").read_text(encoding="utf-8"))
            self.assertEqual(saved_state["coordinator_auth_token"], token)

    def test_near_limit_exact_token_failure_leaves_every_authority_unchanged(self) -> None:
        class Dispatcher:
            def __init__(self) -> None:
                self.token = "existing-token-0123456789"
                self.updates: list[str] = []

            def get_auth_token(self) -> str:
                return self.token

            def update_auth_token(self, value: str) -> None:
                self.updates.append(value)
                self.token = value

        exact_token = "e" * 64
        _placeholder_blob, placeholder_payload = encode_network_join_blob(
            coordinator_url="http://coordinator.test:7830",
            token="preflight-token-0123456789",
            libraries=[],
            created_at_utc="2026-07-23T00:00:00Z",
        )
        placeholder_bytes = len(
            json.dumps(
                placeholder_payload,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        )

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            existing_token = "existing-token-0123456789"
            resolved = _resolved(root, {"NetworkRole": "coordinator", "CoordinatorAuthToken": existing_token})
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            dispatcher = Dispatcher()
            saved_tokens: list[str] = []

            def save_patch(_resolved_paths, request):
                saved_tokens.append(request["changes"]["CoordinatorAuthToken"])
                return SimpleNamespace(ok=True, errors=[], message="saved")

            with patch.object(facade, "_network_dispatcher_for_role", return_value=dispatcher), patch.object(
                facade, "_save_settings_patch_with_network_credentials", side_effect=save_patch
            ), patch("mediapipeline.core.network.facade.generate_token", return_value=exact_token), patch.object(
                join_helpers, "NETWORK_JOIN_BLOB_MAX_DECODED_BYTES", placeholder_bytes
            ):
                result = facade.request_network_coordinator_join_blob(
                    resolved,
                    {
                        "confirm_create": True,
                        "coordinator_url": "http://coordinator.test:7830",
                        "rotate_token": True,
                        "confirm_rotate": True,
                    },
                ).to_mapping()

        self.assertFalse(result["ok"])
        self.assertEqual(saved_tokens, [])
        self.assertEqual(dispatcher.updates, [])
        self.assertEqual(dispatcher.token, existing_token)
        self.assertEqual(service.load_app_state().get("coordinator_auth_token"), None)
        self.assertNotIn(exact_token, json.dumps(result, sort_keys=True))

    def test_exact_join_blob_is_encoded_once_before_rotation_commit(self) -> None:
        class Dispatcher:
            def get_auth_token(self) -> str:
                return "existing-token-0123456789"

            def update_auth_token(self, value: str) -> None:
                events.append(("runtime", value))

        exact_token = "f" * 64
        events: list[tuple[str, str]] = []
        real_encode = encode_network_join_blob

        def encode_once(**kwargs):
            events.append(("encode", str(kwargs["token"])))
            return real_encode(**kwargs)

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            resolved = _resolved(
                root,
                {"NetworkRole": "coordinator", "CoordinatorAuthToken": "existing-token-0123456789"},
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")

            def save_patch(_resolved_paths, request):
                events.append(("config", request["changes"]["CoordinatorAuthToken"]))
                return SimpleNamespace(ok=True, errors=[], message="saved")

            with patch.object(facade, "_network_dispatcher_for_role", return_value=Dispatcher()), patch.object(
                facade, "_save_settings_patch_with_network_credentials", side_effect=save_patch
            ), patch("mediapipeline.core.network.facade.generate_token", return_value=exact_token), patch(
                "mediapipeline.core.network.facade.encode_network_join_blob", side_effect=encode_once
            ):
                result = facade.request_network_coordinator_join_blob(
                    resolved,
                    {
                        "confirm_create": True,
                        "coordinator_url": "http://coordinator.test:7830",
                        "rotate_token": True,
                        "confirm_rotate": True,
                    },
                ).to_mapping()

        self.assertTrue(result["ok"])
        self.assertEqual(events, [("encode", exact_token), ("config", exact_token), ("runtime", exact_token)])
        self.assertNotIn(exact_token, json.dumps(result, sort_keys=True))

    def test_running_coordinator_rotation_commits_one_token_to_all_authorities(self) -> None:
        exact_token = "c" * 64
        existing_token = "existing-token-0123456789"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            service.app_state_path = root / "desktop_app_state.json"
            resolved = _resolved(root, {"NetworkRole": "coordinator", "CoordinatorAuthToken": existing_token})
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._auth_token = existing_token
            dispatcher._app = SimpleNamespace(service=service)
            dispatcher._safe_log_cluster_event = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
            saved_config_tokens: list[str] = []

            def save_patch(_resolved_paths, request):
                saved_config_tokens.append(request["changes"]["CoordinatorAuthToken"])
                return SimpleNamespace(ok=True, errors=[], message="saved")

            with patch.object(facade, "_network_dispatcher_for_role", return_value=dispatcher), patch.object(
                facade, "_save_settings_patch_with_network_credentials", side_effect=save_patch
            ), patch("mediapipeline.core.network.facade.generate_token", return_value=exact_token):
                result = facade.request_network_coordinator_join_blob(
                    resolved,
                    {
                        "confirm_create": True,
                        "coordinator_url": "http://coordinator.test:7830",
                        "rotate_token": True,
                        "confirm_rotate": True,
                    },
                ).to_mapping()

            decoded = decode_network_join_blob(result["data"]["join_blob"])
            app_state_token = service.load_app_state().get("coordinator_auth_token")

        self.assertTrue(result["ok"])
        self.assertEqual(saved_config_tokens, [exact_token])
        self.assertEqual(dispatcher._auth_token, exact_token)
        self.assertEqual(app_state_token, exact_token)
        self.assertEqual(decoded["token"], exact_token)
        self.assertTrue(result["data"]["writes_config"])
        self.assertTrue(result["data"]["writes_app_state"])
        self.assertTrue(result["data"]["running_coordinator_updated"])
        self.assertNotIn(exact_token, json.dumps(result, sort_keys=True))

    def test_invalid_join_blob_input_is_rejected_before_token_rotation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            resolved = _resolved(root, {"NetworkRole": "coordinator", "CoordinatorAuthToken": "existing-token-0123456789"})
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")

            with patch.object(facade, "_coordinator_join_token") as rotate_token:
                result = facade.request_network_coordinator_join_blob(
                    resolved,
                    {
                        "confirm_create": True,
                        "coordinator_url": "not-a-valid-url",
                        "rotate_token": True,
                        "confirm_rotate": True,
                    },
                ).to_mapping()

        self.assertFalse(result["ok"])
        rotate_token.assert_not_called()
        self.assertEqual(service.saved_config_calls, [])

    def test_running_coordinator_rotation_failure_restores_previous_config_token(self) -> None:
        class Dispatcher:
            def __init__(self) -> None:
                self.updates: list[str] = []

            def get_auth_token(self) -> str:
                return "existing-token-0123456789"

            def update_auth_token(self, value: str) -> None:
                self.updates.append(value)
                if value != "existing-token-0123456789":
                    raise RuntimeError("runtime update failed")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            resolved = _resolved(root, {"NetworkRole": "coordinator", "CoordinatorAuthToken": "existing-token-0123456789"})
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            dispatcher = Dispatcher()
            saved_tokens: list[str] = []

            def save_patch(_resolved_paths, request):
                saved_tokens.append(request["changes"]["CoordinatorAuthToken"])
                return SimpleNamespace(ok=True, errors=[], message="saved")

            with patch.object(facade, "_network_dispatcher_for_role", return_value=dispatcher), patch.object(
                facade, "_save_settings_patch_with_network_credentials", side_effect=save_patch
            ):
                result = facade.request_network_coordinator_join_blob(
                    resolved,
                    {
                        "confirm_create": True,
                        "coordinator_url": "http://coordinator.test:7830",
                        "rotate_token": True,
                        "confirm_rotate": True,
                    },
                ).to_mapping()

        self.assertFalse(result["ok"])
        self.assertEqual(saved_tokens[-1], "existing-token-0123456789")
        self.assertEqual(dispatcher.updates[-1], "existing-token-0123456789")

    def test_running_rotation_persistence_failure_rolls_back_config_and_keeps_runtime(self) -> None:
        exact_token = "d" * 64
        existing_token = "existing-token-0123456789"
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            resolved = _resolved(root, {"NetworkRole": "coordinator", "CoordinatorAuthToken": existing_token})
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._auth_token = existing_token
            dispatcher._app = SimpleNamespace(
                service=SimpleNamespace(
                    save_app_state=lambda _data: (_ for _ in ()).throw(RuntimeError("disk read-only"))
                )
            )
            dispatcher._safe_log_cluster_event = lambda *_args, **_kwargs: None  # type: ignore[method-assign]
            saved_config_tokens: list[str] = []

            def save_patch(_resolved_paths, request):
                saved_config_tokens.append(request["changes"]["CoordinatorAuthToken"])
                return SimpleNamespace(ok=True, errors=[], message="saved")

            with patch.object(facade, "_network_dispatcher_for_role", return_value=dispatcher), patch.object(
                facade, "_save_settings_patch_with_network_credentials", side_effect=save_patch
            ), patch("mediapipeline.core.network.facade.generate_token", return_value=exact_token):
                result = facade.request_network_coordinator_join_blob(
                    resolved,
                    {
                        "confirm_create": True,
                        "coordinator_url": "http://coordinator.test:7830",
                        "rotate_token": True,
                        "confirm_rotate": True,
                    },
                ).to_mapping()

        self.assertFalse(result["ok"])
        self.assertEqual(saved_config_tokens, [exact_token, existing_token])
        self.assertEqual(dispatcher._auth_token, existing_token)
        self.assertEqual(result["data"]["join_blob"], "")
        self.assertNotIn(exact_token, json.dumps(result, sort_keys=True))

    def test_local_api_settings_patch_rejects_network_credentials_without_leaking_values(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            resolved = _resolved(
                root,
                {
                    "NetworkRole": "standalone",
                    "CoordinatorAuthToken": "existing-coordinator-secret",
                    "WorkerAuthToken": "existing-worker-secret",
                },
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
            )
            try:
                server.start()
                preview_secret = "submitted-coordinator-secret"
                save_secret = "submitted-worker-secret"
                preview_status, preview_result = _post_json(
                    f"{server.url}/api/settings/preview-patch",
                    {"changes": {"CoordinatorAuthToken": preview_secret}},
                    "test-token",
                )
                save_status, save_result = _post_json(
                    f"{server.url}/api/settings/save-patch",
                    {"changes": {"WorkerAuthToken": save_secret}, "confirm_save": True},
                    "test-token",
                )
            finally:
                server.stop()

        self.assertEqual(preview_status, 200)
        self.assertEqual(save_status, 200)
        self.assertFalse(preview_result["ok"])
        self.assertFalse(save_result["ok"])
        self.assertIn("cannot be changed through Settings Patch", "\n".join(preview_result["errors"]))
        self.assertIn("cannot be changed through Settings Patch", "\n".join(save_result["errors"]))
        serialized_results = json.dumps([preview_result, save_result], sort_keys=True)
        self.assertNotIn(preview_secret, serialized_results)
        self.assertNotIn(save_secret, serialized_results)
        self.assertNotIn("existing-coordinator-secret", serialized_results)
        self.assertNotIn("existing-worker-secret", serialized_results)
        self.assertEqual(service.saved_config_calls, [])

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
        self.assertEqual(result["data"]["effect"], "config-write")
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
