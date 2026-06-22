from __future__ import annotations

import contextlib
import csv
from datetime import datetime, timedelta
import io
import json
import logging
import os
import re
import sys
import tempfile
import threading
import time
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from urllib.parse import quote
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.core.api.commands_process import LocalApiProcessCommandPayloadMixin
from mediapipeline.desktop.api.handler import build_local_api_handler_class
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.local_api_main import BOOTSTRAP_SCHEMA_VERSION, bootstrap_payload, build_backend, main as local_api_main
from mediapipeline.desktop.models import ResolvedPaths, Snapshot
from tests.python.desktop.test_application_facade import (
    DummyFacadeService,
    DummyProc,
    DummyWorkflowFacadeService,
    _render_static_index_html,
    _resolved,
)


def _assert_namespace_export(testcase: unittest.TestCase, source: str, namespace: str, symbol: str) -> None:
    testcase.assertRegex(
        source,
        rf"window\.{re.escape(namespace)}\s*=\s*\{{[\s\S]*?\b{re.escape(symbol)}\b\s*(?:,|:|\n\s*\}})",
    )


COMMAND_HISTORY_ASSET_ORDER = [
    "/assets/commandHistory/formatters.js",
    "/assets/commandHistory/diagnostics.js",
    "/assets/commandHistory.js",
]


class LocalApiServerTests(unittest.TestCase):
    def _get_json(self, url: str, token: str | None = None, extra_headers: dict[str, str] | None = None) -> tuple[int, dict]:
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        headers = dict(extra_headers or {})
        if token:
            headers["Authorization"] = f"Bearer {token}"
        request = Request(url, headers=headers)
        try:
            with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _post_json(self, url: str, payload: dict, token: str | None = None, extra_headers: dict[str, str] | None = None) -> tuple[int, dict]:
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        headers = {"Content-Type": "application/json", **dict(extra_headers or {})}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        body = json.dumps(payload).encode("utf-8")
        request = Request(url, data=body, headers=headers, method="POST")
        try:
            with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
                return response.status, json.loads(response.read().decode("utf-8"))
        except HTTPError as exc:
            return exc.code, json.loads(exc.read().decode("utf-8"))

    def _options(self, url: str, extra_headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        request = Request(url, headers=dict(extra_headers or {}), method="OPTIONS")
        try:
            with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
                return response.status, dict(response.headers.items()), response.read()
        except HTTPError as exc:
            return exc.code, dict(exc.headers.items()), exc.read()

    def _get_raw(self, url: str, extra_headers: dict[str, str] | None = None) -> tuple[int, dict[str, str], bytes]:
        from urllib.error import HTTPError
        from urllib.request import Request, urlopen

        request = Request(url, headers=dict(extra_headers or {}))
        try:
            with urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
                return response.status, dict(response.headers.items()), response.read()
        except HTTPError as exc:
            return exc.code, dict(exc.headers.items()), exc.read()

    def test_local_api_server_suppresses_client_disconnect_tracebacks(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(facade, token="test-token")
            try:
                server.start()
                http_server = server._server
                self.assertIsNotNone(http_server)
                assert http_server is not None

                disconnect_stderr = io.StringIO()
                with contextlib.redirect_stderr(disconnect_stderr):
                    try:
                        raise ConnectionResetError(10054, "connection reset by peer")
                    except ConnectionResetError:
                        http_server.handle_error(object(), ("127.0.0.1", 54321))

                runtime_stderr = io.StringIO()
                with contextlib.redirect_stderr(runtime_stderr):
                    try:
                        raise RuntimeError("boom")
                    except RuntimeError:
                        http_server.handle_error(object(), ("127.0.0.1", 54321))
            finally:
                server.stop()

        self.assertEqual(disconnect_stderr.getvalue(), "")
        self.assertIn("RuntimeError: boom", runtime_stderr.getvalue())

    def test_local_api_close_readiness_is_unsafe_when_workspace_is_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="test-token")
            try:
                server.start()
                status, payload = self._get_json(f"{server.url}/api/backend/close-readiness", token="test-token")
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_version"], "desktop_close_readiness.v1")
        self.assertFalse(payload["safe_to_close"])
        self.assertTrue(payload["active_work"])
        self.assertEqual(payload["state"], "unknown")
        self.assertIn("resolved paths are unavailable", payload["reason"])
        self.assertTrue(payload["warnings"])

    def test_browser_index_uses_http_only_cookie_without_rendering_token(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                index_status, index_headers, index_body = self._get_raw(f"{server.url}/")
                cookie = index_headers.get("Set-Cookie", "")
                contract_status, contract = self._get_json(
                    f"{server.url}/api/contract",
                    extra_headers={"Cookie": cookie.split(";", 1)[0]},
                )
            finally:
                server.stop()

        self.assertEqual(index_status, 200)
        self.assertIn("MediaPipelineAuth=", cookie)
        self.assertIn("HttpOnly", cookie)
        self.assertIn("SameSite=Strict", cookie)
        self.assertNotIn(b"test-token", index_body)
        self.assertEqual(contract_status, 200)
        self.assertEqual(contract["schema_version"], "desktop_local_api_contract.v1")

    def test_browser_index_render_failure_does_not_set_auth_cookie(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
                static_root=root / "missing-static-root",
            )
            try:
                server.start()
                index_status, index_headers, index_body = self._get_raw(f"{server.url}/")
            finally:
                server.stop()

        self.assertEqual(index_status, 404)
        self.assertEqual(index_headers.get("Set-Cookie", ""), "")
        self.assertIn(b"local web assets are not installed", index_body)

    def test_local_api_shutdown_blocks_when_workspace_is_unresolved(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            shutdown_event = threading.Event()
            server = LocalApiServer(facade, token="test-token", shutdown_request=shutdown_event.set)
            try:
                server.start()
                status, payload = self._post_json(
                    f"{server.url}/api/backend/shutdown",
                    {"reason": "test"},
                    token="test-token",
                )
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(payload["command"], "backend.shutdown")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["severity"], "error")
        self.assertEqual(payload["data"]["safe_to_close"], False)
        self.assertEqual(payload["data"]["state"], "unknown")
        self.assertIn("resolved paths are unavailable", payload["errors"][0])
        self.assertFalse(shutdown_event.wait(0.2))

    def test_rename_clean_filename_preview_get_route_uses_backend_cleaner_without_command_journal(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="rename-token")
            try:
                server.start()
                query = "&".join(
                    f"{key}={quote(value, safe='')}"
                    for key, value in {
                        "filename": "Together.2025.1080p.WEBRip.10Bit.DDP5.1.x265-NeoNoir.mkv",
                        "movie_filter_terms": json.dumps({"release_groups": ["neonoir"]}),
                    }.items()
                )
                status, payload = self._get_json(
                    f"{server.url}/api/rename/clean-filename-preview?{query}",
                    token="rename-token",
                )
                catalog_status, catalog = self._get_json(
                    f"{server.url}/api/rename/movie-cleaning-filters",
                    token="rename-token",
                )
                split_catalog_status, split_catalog = self._get_json(
                    f"{server.url}/api/rename/cleaning-filters",
                    token="rename-token",
                )
                tv_query = "&".join(
                    f"{key}={quote(value, safe='')}"
                    for key, value in {
                        "mode": "tv",
                        "source_folder": "The Web S01 1080p WEB-DL-TTGA",
                        "filename": "S01E01-Pilot.1080p.WEB-DL-TTGA.mkv",
                        "tv_filter_terms": json.dumps({"release_groups": ["TTGA"]}),
                    }.items()
                )
                tv_status, tv_payload = self._get_json(
                    f"{server.url}/api/rename/clean-filename-preview?{tv_query}",
                    token="rename-token",
                )
                history_status, history = self._get_json(f"{server.url}/api/commands?limit=5", token="rename-token")
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_version"], "desktop_rename_clean_filename_preview.v1")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["target_name"], "Together (2025).mkv")
        self.assertEqual(payload["preview_source"], "backend_movie_cleaner")
        self.assertTrue(payload["movie_filter_terms_enabled"])
        self.assertEqual(payload["movie_filter_terms_mode"], "staged")
        self.assertEqual(payload["rename_cleaning_policy_source"], "staged")
        self.assertIn("no filesystem paths", payload["mutation_boundary"])
        self.assertEqual(catalog_status, 200)
        self.assertEqual(catalog["schema_version"], "desktop_rename_movie_filter_catalog.v1")
        self.assertEqual(catalog["movie_filter_terms_mode"], "saved")
        self.assertIn("cmrg", catalog["default_terms"]["release_groups"])
        self.assertIn("neonoir", catalog["default_terms"]["release_groups"])
        self.assertEqual(split_catalog_status, 200)
        self.assertEqual(split_catalog["schema_version"], "desktop_rename_cleaning_filter_catalog.v1")
        self.assertIn("movie", split_catalog)
        self.assertIn("tv", split_catalog)
        self.assertIn("ttga", split_catalog["tv"]["default_terms"]["release_groups"])
        self.assertEqual(tv_status, 200)
        self.assertEqual(tv_payload["target_name"], "The Web - S01E01 - Pilot.mkv")
        self.assertEqual(tv_payload["preview_source"], "backend_tv_cleaner")
        self.assertEqual(tv_payload["tv_filter_terms_mode"], "staged")
        self.assertEqual(history_status, 200)
        self.assertEqual(history["entries"], [])

    def test_rename_clean_filename_preview_rejects_invalid_query_json_without_command_journal(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="rename-token")
            try:
                server.start()
                rejected: list[tuple[int, dict]] = []
                for key, value in (
                    ("movie_filter_options", "NaN"),
                    ("movie_filter_options", "Infinity"),
                    ("movie_filter_terms", '{"release_groups":'),
                ):
                    query = "&".join(
                        f"{query_key}={quote(query_value, safe='')}"
                        for query_key, query_value in {
                            "filename": "Together.2025.1080p.WEBRip.10Bit.DDP5.1.x265-NeoNoir.mkv",
                            key: value,
                        }.items()
                    )
                    rejected.append(
                        self._get_json(
                            f"{server.url}/api/rename/clean-filename-preview?{query}",
                            token="rename-token",
                        )
                    )
                history_status, history = self._get_json(f"{server.url}/api/commands?limit=5", token="rename-token")
            finally:
                server.stop()

        for status, payload in rejected:
            self.assertEqual(status, 400)
            self.assertEqual(payload["path"], "/api/rename/clean-filename-preview")
            self.assertIn("invalid query parameter", payload["error"])
        self.assertIn("non-finite JSON value is not allowed", rejected[0][1]["error"])
        self.assertIn("non-finite JSON value is not allowed", rejected[1][1]["error"])
        self.assertIn("movie_filter_terms", rejected[2][1]["error"])
        self.assertEqual(history_status, 200)
        self.assertEqual(history["entries"], [])

    def test_rename_filter_settings_persist_and_feed_saved_preview_policy(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "RoutingProfile": "plex_direct_stream",
                "OutputContainer": "mkv",
            }
            server = LocalApiServer(facade, token="rename-token", resolved_provider=lambda: resolved)
            changes = {
                "RenameMovieFilterOptions": {
                    "video_source": True,
                    "audio_channels": True,
                    "editions": True,
                    "file_size": True,
                    "services_containers": True,
                    "languages_subs_dubs": True,
                    "release_groups": True,
                },
                "RenameMovieFilterTerms": {
                    "release_groups": ["SupaCvnt", "BYNDR"],
                    "services_containers": ["MA"],
                    "languages_subs_dubs": ["ita", "eng", "sub", "dub"],
                    "unknown": ["ignored"],
                },
                "RenameMovieRemoveTerms": ["sample", "", "sample", "behind the scenes"],
                "RenameTVFilterOptions": {
                    "video_source": True,
                    "audio_channels": True,
                    "release_flags": True,
                    "services_containers": True,
                    "languages_subs_dubs": True,
                    "release_groups": True,
                },
                "RenameTVFilterTerms": {
                    "release_groups": ["TTGA", "ttga"],
                    "release_flags": ["uncensored"],
                    "unknown": ["ignored"],
                },
                "RenameTVRemoveTerms": ["ova", "", "ova", "special"],
            }
            try:
                server.start()
                preview_status, preview_payload = self._post_json(
                    f"{server.url}/api/settings/preview-patch",
                    {"changes": changes},
                    token="rename-token",
                )
                save_status, save_payload = self._post_json(
                    f"{server.url}/api/settings/save-patch",
                    {"changes": changes, "confirm_save": True},
                    token="rename-token",
                )
                saved_values = dict(service.saved_config_calls[-1]["config_values"])
                resolved.config_data = saved_values
                catalog_status, catalog = self._get_json(
                    f"{server.url}/api/rename/cleaning-filters",
                    token="rename-token",
                )
                filename_query = quote(
                    "Hoppers.2026.2160p.MA.WEB-DL.DDP5.1.Atmos.DV.HDR.H.265-BYNDR.mkv",
                    safe="",
                )
                saved_preview_status, saved_preview = self._get_json(
                    f"{server.url}/api/rename/clean-filename-preview?filename={filename_query}",
                    token="rename-token",
                )
                tv_filename_query = "&".join(
                    f"{key}={quote(value, safe='')}"
                    for key, value in {
                        "mode": "tv",
                        "source_folder": "The Web S01 1080p WEB-DL-TTGA",
                        "filename": "S01E01-Pilot.1080p.WEB-DL-TTGA.mkv",
                    }.items()
                )
                saved_tv_preview_status, saved_tv_preview = self._get_json(
                    f"{server.url}/api/rename/clean-filename-preview?{tv_filename_query}",
                    token="rename-token",
                )
                staged_query = "&".join(
                    f"{key}={quote(value, safe='')}"
                    for key, value in {
                        "filename": "Iron.Lung.2026.1080p.WEBRip.x265.6CH-SupaCvnt.mkv",
                        "movie_filter_terms": json.dumps({"release_groups": ["SupaCvnt"]}),
                    }.items()
                )
                staged_preview_status, staged_preview = self._get_json(
                    f"{server.url}/api/rename/clean-filename-preview?{staged_query}",
                    token="rename-token",
                )
            finally:
                server.stop()

        self.assertEqual(preview_status, 200)
        self.assertTrue(preview_payload["ok"])
        self.assertEqual(save_status, 200)
        self.assertTrue(save_payload["ok"])
        self.assertEqual(saved_values["RenameMovieFilterTerms"]["release_groups"], ["SupaCvnt", "BYNDR"])
        self.assertEqual(saved_values["RenameMovieFilterTerms"]["services_containers"], ["MA"])
        self.assertEqual(saved_values["RenameMovieFilterTerms"]["languages_subs_dubs"], ["ita", "eng", "sub", "dub"])
        self.assertNotIn("unknown", saved_values["RenameMovieFilterTerms"])
        self.assertEqual(saved_values["RenameMovieRemoveTerms"], ["sample", "behind the scenes"])
        self.assertEqual(saved_values["RenameTVFilterTerms"]["release_groups"], ["TTGA"])
        self.assertEqual(saved_values["RenameTVFilterTerms"]["release_flags"], ["uncensored"])
        self.assertNotIn("unknown", saved_values["RenameTVFilterTerms"])
        self.assertEqual(saved_values["RenameTVRemoveTerms"], ["ova", "special"])
        self.assertEqual(catalog_status, 200)
        self.assertEqual(catalog["schema_version"], "desktop_rename_cleaning_filter_catalog.v1")
        self.assertEqual(catalog["movie"]["saved_terms"]["release_groups"], ["SupaCvnt", "BYNDR"])
        self.assertEqual(catalog["movie"]["saved_remove_terms"], ["sample", "behind the scenes"])
        self.assertEqual(catalog["tv"]["saved_terms"]["release_groups"], ["TTGA"])
        self.assertEqual(catalog["tv"]["saved_remove_terms"], ["ova", "special"])
        self.assertEqual(saved_preview_status, 200)
        self.assertEqual(saved_preview["target_name"], "Hoppers (2026).mkv")
        self.assertEqual(saved_preview["rename_cleaning_policy_source"], "saved")
        self.assertEqual(saved_tv_preview_status, 200)
        self.assertEqual(saved_tv_preview["target_name"], "The Web - S01E01 - Pilot.mkv")
        self.assertEqual(saved_tv_preview["rename_cleaning_policy_source"], "saved")
        self.assertEqual(staged_preview_status, 200)
        self.assertEqual(staged_preview["target_name"], "Iron Lung (2026).mkv")
        self.assertEqual(staged_preview["rename_cleaning_policy_source"], "staged")

    def test_local_api_rejects_query_string_tokens(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="test-token")
            try:
                server.start()
                status, payload = self._get_json(f"{server.url}/api/backend/close-readiness?token=test-token")
                header_status, _ = self._get_json(f"{server.url}/api/backend/close-readiness", token="test-token")
            finally:
                server.stop()

        self.assertEqual(status, 401)
        self.assertEqual(payload["error"], "unauthorized")
        self.assertEqual(header_status, 200)

    def test_local_api_rejects_invalid_host_and_cross_origin_posts(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="test-token")
            try:
                server.start()
                bad_host_status, bad_host = self._get_json(
                    f"{server.url}/api/health",
                    extra_headers={"Host": "evil.example"},
                )
                bad_origin_status, bad_origin = self._post_json(
                    f"{server.url}/api/settings/reload",
                    {},
                    token="test-token",
                    extra_headers={"Origin": "http://evil.example"},
                )
                good_origin_status, _ = self._post_json(
                    f"{server.url}/api/settings/reload",
                    {},
                    token="test-token",
                    extra_headers={"Origin": f"http://127.0.0.1:{server.port}"},
                )
            finally:
                server.stop()

        self.assertEqual(bad_host_status, 400)
        self.assertEqual(bad_host["error"], "invalid host")
        self.assertEqual(bad_origin_status, 403)
        self.assertEqual(bad_origin["error"], "invalid origin")
        self.assertEqual(good_origin_status, 200)

    def test_local_api_options_reflects_allowed_origin_and_security_headers(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="test-token")
            try:
                server.start()
                origin = f"http://127.0.0.1:{server.port}"
                status, headers, body = self._options(
                    f"{server.url}/api/settings/reload",
                    extra_headers={"Origin": origin},
                )
            finally:
                server.stop()

        self.assertEqual(status, 204)
        self.assertEqual(body, b"")
        self.assertEqual(headers["Access-Control-Allow-Origin"], origin)
        self.assertEqual(headers["Vary"], "Origin")
        self.assertIn("X-MediaPipeline-Token", headers["Access-Control-Allow-Headers"])
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")

    def test_local_api_no_token_requires_loopback_and_explicit_env(self) -> None:
        with patch.dict(os.environ, {}, clear=True), patch("builtins.print"):
            missing_env = local_api_main(["--no-token", "--host", "127.0.0.1"])
        with patch.dict(os.environ, {"MEDIAPIPELINE_ALLOW_NO_TOKEN_DEV": "1"}, clear=True), patch("builtins.print"):
            non_loopback = local_api_main(["--no-token", "--host", "0.0.0.0"])

        self.assertEqual(missing_env, 2)
        self.assertEqual(non_loopback, 2)

    def test_local_api_request_threads_are_not_daemonized(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="test-token")
            try:
                server.start()
                http_server = server._server  # type: ignore[attr-defined]
                self.assertIsNotNone(http_server)
                assert http_server is not None
                self.assertFalse(http_server.daemon_threads)
                self.assertTrue(getattr(http_server, "block_on_close", True))
            finally:
                server.stop()

    def test_local_api_diagnostics_tail_reads_allowlisted_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            (root / "cluster.log").write_text("coordinator started\nworker warning\n", encoding="utf-8")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                status, payload = self._get_json(f"{server.url}/api/diagnostics/tail?target=cluster_log&max_bytes=4096", token="test-token")
                rejected_status, rejected = self._get_json(f"{server.url}/api/diagnostics/tail?target=C%3A%5Csecret.txt", token="test-token")
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_version"], "desktop_diagnostics_tail.v1")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["target"], "cluster_log")
        self.assertIn("worker warning", payload["text"])
        self.assertEqual(payload["evidence"]["evidence_authority"], "backend")
        self.assertEqual(payload["evidence"]["operator_status"], "review")
        self.assertEqual(payload["evidence"]["warning_count"], 1)
        self.assertEqual(rejected_status, 200)
        self.assertFalse(rejected["ok"])
        self.assertIn("not allowed", "\n".join(rejected["errors"]))
        self.assertEqual(rejected["evidence"]["operator_status"], "blocked")

    def test_local_api_diagnostics_state_summary_reads_backend_allowlist(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.queue_snapshot_path = root / "State" / "Progress" / "queue_snapshot.json"
            resolved.pending_push_path = root / "State" / "PendingPublish"
            assert resolved.queue_snapshot_path is not None
            assert resolved.pending_push_path is not None
            resolved.queue_snapshot_path.parent.mkdir(parents=True)
            resolved.pending_push_path.mkdir(parents=True)
            resolved.queue_snapshot_path.write_text(json.dumps({"queue": [1, 2]}), encoding="utf-8")
            (resolved.pending_push_path / "parked.json").write_text("{}", encoding="utf-8")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                status, payload = self._get_json(f"{server.url}/api/diagnostics/state-summary", token="test-token")
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_version"], "desktop_diagnostics_state_summary.v1")
        self.assertEqual(payload["autonomy_health"]["schema_version"], "desktop_autonomy_health.v1")
        self.assertIn("arbitrary paths", payload["guardrail"])
        rows = {row["target"]: row for row in payload["targets"]}
        self.assertEqual(rows["queue_snapshot"]["status"], "ok")
        self.assertEqual(rows["pending_publish"]["kind"], "directory")
        self.assertTrue(rows["pending_publish"]["recent_entries"])

    def test_local_api_health_failure_returns_json_error_envelope(self) -> None:
        class FailingHealthFacade:
            app_version = "v6-test"

            def get_health(self, _resolved: object) -> object:
                raise RuntimeError("health unavailable")

        logger_name = "test.local_api.health"
        server = LocalApiServer(
            FailingHealthFacade(),  # type: ignore[arg-type]
            token="test-token",
            logger=logging.getLogger(logger_name),
        )
        try:
            server.start()
            with self.assertLogs(logger_name, level="ERROR") as logs:
                status, payload = self._get_json(f"{server.url}/api/health")
        finally:
            server.stop()

        self.assertEqual(status, 500)
        self.assertEqual(payload["error"], "internal route error")
        self.assertEqual(payload["path"], "/api/health")
        self.assertRegex(payload["error_id"], r"^[0-9a-f]{12}$")
        self.assertIn("local API route failed: /api/health", "\n".join(logs.output))
        self.assertIn("health unavailable", "\n".join(logs.output))

    def test_local_api_send_json_rejects_nonfinite_response_payload(self) -> None:
        records: list[dict[str, object]] = []

        class Journal:
            def record(self, payload: dict[str, object]) -> None:
                records.append(payload)

        logger_name = "test.local_api.strict_json"
        owner = type(
            "Owner",
            (),
            {
                "logger": logging.getLogger(logger_name),
                "command_journal": Journal(),
            },
        )()
        handler_cls = build_local_api_handler_class(owner)
        handler = handler_cls.__new__(handler_cls)
        sent: list[tuple[bytes, int, str]] = []
        handler._send_bytes = lambda body, *, status=200, content_type="application/octet-stream": sent.append(  # type: ignore[method-assign]
            (body, status, content_type)
        )

        with self.assertLogs(logger_name, level="ERROR") as logs:
            handler._send_json({"value": float("nan")})

        self.assertEqual(len(sent), 1)
        body, status, content_type = sent[0]
        payload = json.loads(body.decode("utf-8"))
        self.assertEqual(status, 500)
        self.assertEqual(content_type, "application/json; charset=utf-8")
        self.assertEqual(payload["path"], "local-api response")
        self.assertEqual(payload["error"], "internal route error")
        self.assertRegex(payload["error_id"], r"^[0-9a-f]{12}$")
        self.assertEqual(records, [])
        self.assertIn("local API attempted to send a non-strict JSON response", "\n".join(logs.output))
        self.assertIn("Out of range float values", "\n".join(logs.output))

    def test_local_api_rejects_wrong_json_content_type_without_command_journal_entry(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(facade, token="test-token")
            try:
                server.start()
                status, payload = self._post_json(
                    f"{server.url}/api/settings/reload",
                    {},
                    token="test-token",
                    extra_headers={"Content-Type": "text/plain"},
                )
                commands_status, commands = self._get_json(f"{server.url}/api/commands?limit=10", token="test-token")
            finally:
                server.stop()

        self.assertEqual(status, 415)
        self.assertEqual(payload, {"error": "unsupported media type; use application/json"})
        self.assertEqual(commands_status, 200)
        self.assertEqual(commands["entries"], [])

    def test_local_api_network_lifecycle_dry_run_does_not_write_command_journal(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            resolved.config_data = {
                "NetworkRole": "coordinator",
                "CoordinatorPort": 7830,
                "CoordinatorBindAddress": "127.0.0.1",
                "CoordinatorHeartbeatTimeoutMins": 5,
            }
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
            )
            try:
                server.start()
                status, payload = self._post_json(
                    f"{server.url}/api/network/coordinator/start-dry-run",
                    {"reason": "operator check"},
                    token="test-token",
                )
                commands_status, commands = self._get_json(f"{server.url}/api/commands?limit=10", token="test-token")
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertTrue(payload["data"]["dry_run_only"])
        self.assertEqual(payload["data"]["effect"], "none")
        self.assertTrue(payload["data"]["suppress_command_journal"])
        self.assertEqual(commands_status, 200)
        self.assertEqual(commands["entries"], [])

    def test_local_api_repair_reconcile_dry_run_routes_return_schema_and_suppress_journal(self) -> None:
        from tests.python.desktop.test_repair_reconcile_dry_run import (
            _assert_dry_run_shape,
            _assert_startup_reconciliation_shape,
            _completed_fixture,
            _pending_fixture,
        )

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            completed_resolved, _completed_files = _completed_fixture(root)
            pending_resolved, _pending_files = _pending_fixture(root, orphan_payload=True)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")

            def resolved_provider() -> ResolvedPaths:
                completed_resolved.pending_push_path = pending_resolved.pending_push_path
                completed_resolved.state_root = pending_resolved.state_root
                return completed_resolved

            completed_preview = facade.get_completed_preview(completed_resolved).to_mapping()
            pending_preview = facade.get_pending_publish_preview(pending_resolved).to_mapping()
            completed_row_key = completed_preview["rows"][0]["row_key"]
            pending_row_key = pending_preview["rows"][0]["row_key"]
            server = LocalApiServer(facade, token="test-token", resolved_provider=resolved_provider)
            try:
                server.start()
                route_payloads = {
                    "/api/completed/reconcile-manifest-dry-run": (
                        {"scope": "selected", "row_key": completed_row_key},
                        "completed.reconcile_manifest",
                    ),
                    "/api/completed/repair-sidecar-metadata-dry-run": (
                        {"scope": "selected", "row_key": completed_row_key},
                        "completed.repair_sidecar_metadata",
                    ),
                    "/api/pending-publish/repair-manifest-dry-run": (
                        {"scope": "all", "limit": 25},
                        "pending_publish.repair_manifest",
                    ),
                    "/api/pending-publish/reconcile-orphan-payloads-dry-run": (
                        {"scope": "selected", "row_key": pending_row_key},
                        "pending_publish.reconcile_orphan_payloads",
                    ),
                    "/api/startup/reconcile-dry-run": (
                        {"scope": "all", "limit": 25},
                        "startup.reconcile_state",
                    ),
                }
                responses = {}
                for route, (body, _candidate) in route_payloads.items():
                    status, payload = self._post_json(f"{server.url}{route}", body, token="test-token")
                    self.assertEqual(status, 200, route)
                    self.assertTrue(payload["ok"], route)
                    responses[route] = payload
                commands_status, commands = self._get_json(f"{server.url}/api/commands?limit=10", token="test-token")
            finally:
                server.stop()

        for route, (_body, candidate) in route_payloads.items():
            with self.subTest(route=route):
                if candidate == "startup.reconcile_state":
                    _assert_startup_reconciliation_shape(self, responses[route]["data"])
                else:
                    _assert_dry_run_shape(self, responses[route]["data"], candidate)
        self.assertEqual(commands_status, 200)
        self.assertEqual(commands["entries"], [])

    def test_local_api_settings_reload_failure_is_logged(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            logger_name = "test.local_api.settings_reload"
            long_error = "reload broke " + ("x" * 2500)

            def fail_reload() -> ResolvedPaths:
                raise RuntimeError(long_error)

            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_reload=fail_reload,
                logger=logging.getLogger(logger_name),
            )
            try:
                server.start()
                with self.assertLogs(logger_name, level="ERROR") as logs:
                    status, payload = self._post_json(
                        f"{server.url}/api/settings/reload",
                        {},
                        token="test-token",
                    )
            finally:
                server.stop()

        self.assertEqual(status, 200)
        self.assertEqual(payload["command"], "settings.reload")
        self.assertFalse(payload["ok"])
        self.assertIn("reload broke", payload["message"])
        self.assertLessEqual(len(payload["errors"][0]), 2000)
        self.assertIn("local API settings reload failed", "\n".join(logs.output))

    def test_local_api_process_commands_require_token_before_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                no_token_status, no_token = self._post_json(
                    f"{server.url}/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 3},
                )
                wrong_token_status, wrong_token = self._post_json(
                    f"{server.url}/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 3},
                    token="wrong-token",
                )
                side_effect_before_auth = hasattr(service, "started_pipeline")
                ok_status, ok = self._post_json(
                    f"{server.url}/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 3},
                    token="test-token",
                )
            finally:
                server.stop()

        self.assertEqual(no_token_status, 401)
        self.assertEqual(no_token["error"], "unauthorized")
        self.assertEqual(wrong_token_status, 401)
        self.assertEqual(wrong_token["error"], "unauthorized")
        self.assertFalse(side_effect_before_auth)
        self.assertEqual(ok_status, 200)
        self.assertEqual(ok["command"], "pipeline.start")
        self.assertTrue(hasattr(service, "started_pipeline"))
        self.assertEqual(service.started_pipeline["mode"], "validate")

    def test_local_api_rejects_invalid_command_payload_before_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                status, payload = self._post_json(
                    f"{server.url}/api/pipeline/start",
                    {"mode": "validate", "extra_args": "-NoDeleteSource", "token": "secret-value"},
                    token="test-token",
                )
                commands_status, commands = self._get_json(f"{server.url}/api/commands?limit=5", token="test-token")
            finally:
                server.stop()

        self.assertEqual(status, 400)
        self.assertEqual(payload["path"], "/api/pipeline/start")
        self.assertIn("extra_args", payload["error"])
        self.assertIn("Extra inputs are not permitted", payload["error"])
        self.assertFalse(hasattr(service, "started_pipeline"))
        self.assertEqual(commands_status, 200)
        self.assertEqual(commands["schema_version"], "desktop_command_history.v1")
        self.assertEqual(commands["count"], 1)
        entry = commands["entries"][0]
        self.assertEqual(entry["command"], "local_api.validation_failed")
        self.assertFalse(entry["ok"])
        self.assertEqual(entry["severity"], "error")
        self.assertEqual(entry["data"]["path"], "/api/pipeline/start")
        self.assertEqual(entry["request"]["token"], "<redacted>")
        self.assertEqual(entry["request"]["extra_args"], "-NoDeleteSource")

    def test_local_api_route_exception_is_recorded_in_command_journal(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)

            def fail_start(_resolved_paths: ResolvedPaths, _request: dict) -> object:
                raise RuntimeError("backend exploded with sensitive diagnostic detail")

            facade.start_pipeline_process = fail_start  # type: ignore[method-assign]
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
                command_journal_path=root / "RunLogs" / "local_api_command_history.json",
            )
            try:
                server.start()
                status, payload = self._post_json(
                    f"{server.url}/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                    token="test-token",
                )
                commands_status, commands = self._get_json(f"{server.url}/api/commands?limit=5", token="test-token")
            finally:
                server.stop()

        self.assertEqual(status, 500)
        self.assertEqual(payload["error"], "internal route error")
        self.assertEqual(payload["path"], "/api/pipeline/start")
        self.assertRegex(payload["error_id"], r"^[0-9a-f]{12}$")
        self.assertEqual(commands_status, 200)
        self.assertEqual(commands["schema_version"], "desktop_command_history.v1")
        self.assertEqual(commands["count"], 1)
        entry = commands["entries"][0]
        self.assertEqual(entry["command"], "local_api.route_exception")
        self.assertFalse(entry["ok"])
        self.assertEqual(entry["severity"], "error")
        self.assertEqual(entry["refresh_hint"], "diagnostics")
        self.assertEqual(entry["errors"], ["Internal route error."])
        self.assertEqual(entry["data"]["path"], "/api/pipeline/start")
        self.assertEqual(entry["data"]["status"], 500)
        self.assertEqual(entry["data"]["error_id"], payload["error_id"])
        self.assertEqual(entry["request"]["mode"], "validate")
        self.assertEqual(entry["request"]["sleep_seconds"], 1)
        self.assertNotIn("backend exploded", json.dumps(entry, sort_keys=True))
        persistence = commands["journal_persistence"]
        self.assertFalse(persistence["degraded"])
        self.assertEqual(persistence["json"]["status"], "ok")

    def test_local_api_scheduled_continuous_start_arms_backend_stop_watcher(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            service.save_app_state({"schedule_enabled": True, "schedule_grid": service.default_schedule_grid()})
            deadline = (datetime.now() + timedelta(seconds=60)).replace(microsecond=0).isoformat()
            service.evaluate_schedule = lambda _enabled, _grid: {  # type: ignore[method-assign]
                "enabled": True,
                "allowed_now": True,
                "status_text": f"Schedule: Allowed now until {deadline}",
                "current_window_end": deadline,
                "next_allowed_start": datetime.now().replace(microsecond=0).isoformat(),
                "next_allowed_end": deadline,
                "next_transition": deadline,
            }
            service.find_related_pipeline_processes = lambda _resolved_arg: []  # type: ignore[method-assign]
            service.read_progress = lambda _resolved_arg: {}  # type: ignore[method-assign]
            service.is_progress_stale = lambda _progress: True  # type: ignore[method-assign]
            service.read_audit_progress = lambda _resolved_arg: {}  # type: ignore[method-assign]
            service.is_audit_progress_stale = lambda _progress: True  # type: ignore[method-assign]
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            service.snapshot = Snapshot(
                resolved=resolved,
                current_activity="Ready.",
                status_summary="Idle",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Completed", "CurrentStage": "completed"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                status, payload = self._post_json(
                    f"{server.url}/api/pipeline/start",
                    {"mode": "continuous", "sleep_seconds": 3},
                    token="test-token",
                )
                armed_state = facade._schedule_stop_watcher.state()  # type: ignore[attr-defined]
                schedule_status, schedule_payload = self._get_json(f"{server.url}/api/schedule", token="test-token")
                close_status, close_payload = self._get_json(f"{server.url}/api/backend/close-readiness", token="test-token")
            finally:
                server.stop()
            stopped_state = facade._schedule_stop_watcher.state()  # type: ignore[attr-defined]

        self.assertEqual(status, 200)
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["data"]["mode"], "continuous")
        self.assertEqual(service.started_pipeline["mode"], "continuous")
        self.assertEqual(armed_state.status, "armed")
        self.assertEqual(armed_state.pid, 24680)
        self.assertEqual(armed_state.deadline, deadline)
        self.assertGreater(armed_state.generation, 0)
        self.assertEqual(schedule_status, 200)
        self.assertEqual(schedule_payload["continuous_watcher"]["status"], "armed")
        self.assertEqual(schedule_payload["continuous_watcher"]["pid"], 24680)
        self.assertEqual(schedule_payload["continuous_watcher"]["generation"], armed_state.generation)
        self.assertEqual(close_status, 200)
        self.assertFalse(close_payload["safe_to_close"])
        self.assertTrue(close_payload["active_work"])
        self.assertIn("schedule-stop watcher is armed", close_payload["reason"])
        self.assertEqual(close_payload["continuous_watcher"]["status"], "armed")
        self.assertEqual(close_payload["continuous_watcher"]["pid"], 24680)
        self.assertEqual(close_payload["continuous_watcher"]["generation"], armed_state.generation)
        self.assertEqual(stopped_state.status, "canceled")

    def test_local_api_health_is_public_and_snapshot_requires_token(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            resolved = _resolved(root)
            shutdown_event = threading.Event()
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
                shutdown_request=shutdown_event.set,
                startup_progress={
                    "schema_version": "desktop_startup_progress.v1",
                    "status": "complete",
                    "completed_steps": 1,
                    "total_steps": 1,
                    "steps": [{"id": "server_listening", "label": "Start local API listener", "status": "complete"}],
                },
            )
            try:
                server.start()
                health_status, health = self._get_json(f"{server.url}/api/health")
                contract_denied_status, contract_denied = self._get_json(f"{server.url}/api/contract")
                contract_status, contract = self._get_json(f"{server.url}/api/contract", token="test-token")
                denied_status, denied = self._get_json(f"{server.url}/api/snapshot")
                snapshot_status, snapshot = self._get_json(f"{server.url}/api/snapshot", token="test-token")
                close_status, close_readiness = self._get_json(f"{server.url}/api/backend/close-readiness", token="test-token")
                launch_preflight_status, launch_preflight = self._get_json(
                    f"{server.url}/api/launch/preflight?target=pipeline&mode=validate&sleep_seconds=3",
                    token="test-token",
                )
                telemetry_status, telemetry = self._get_json(f"{server.url}/api/telemetry", token="test-token")
                settings_status, settings = self._get_json(f"{server.url}/api/settings/workspace", token="test-token")
                network_workers_status, network_workers = self._get_json(f"{server.url}/api/network/workers", token="test-token")
                shutdown_status, shutdown = self._post_json(
                    f"{server.url}/api/backend/shutdown",
                    {"reason": "test"},
                    token="test-token",
                )
            finally:
                server.stop()

        self.assertEqual(health_status, 200)
        self.assertEqual(health["app_version"], "v6-test")
        self.assertIn("command-history", health["capabilities"])
        self.assertEqual(health["startup_progress"]["schema_version"], "desktop_startup_progress.v1")
        self.assertEqual(health["startup_progress"]["status"], "complete")
        self.assertEqual(contract_denied_status, 401)
        self.assertEqual(contract_denied["error"], "unauthorized")
        self.assertEqual(contract_status, 200)
        self.assertEqual(contract["schema_version"], "desktop_local_api_contract.v1")
        self.assertEqual(contract["app_version"], "v6-test")
        self.assertIn("/api/health", contract["auth"]["public_routes"])
        self.assertIn("/api/pipeline/start", contract["auth"]["token_routes"])
        self.assertIn("/api/backend/close-readiness", contract["auth"]["token_routes"])
        self.assertIn("/api/launch/preflight", contract["auth"]["token_routes"])
        self.assertIn("/api/commands", contract["auth"]["token_routes"])
        self.assertIn("/api/network/workers", contract["auth"]["token_routes"])
        self.assertIn("/api/network/worker/test-connection", contract["auth"]["token_routes"])
        self.assertIn("/api/audit-controls", contract["auth"]["token_routes"])
        self.assertIn("/api/audit/export-rerun-csv", contract["auth"]["token_routes"])
        self.assertEqual(contract["network_lifecycle_summary"]["status"], "backend_lifecycle_routes_available_provider_guarded")
        self.assertTrue(contract["network_lifecycle_summary"]["mutation_enabled"])
        self.assertTrue(contract["network_lifecycle_summary"]["frontend_allowed"])
        network_lifecycle_commands = {item["candidate_command"] for item in contract["network_lifecycle_contracts"]}
        self.assertIn("network.coordinator.start", network_lifecycle_commands)
        self.assertIn("network.coordinator.stop", network_lifecycle_commands)
        self.assertIn("network.worker.polling_lifecycle", network_lifecycle_commands)
        for lifecycle_contract in contract["network_lifecycle_contracts"]:
            self.assertEqual(lifecycle_contract["dry_run_contract"]["effect"], "none")
            self.assertIn("dry_run_only", lifecycle_contract["dry_run_contract"]["required_result_fields"])
            self.assertTrue(lifecycle_contract["rollback_contract"]["journal_required"])
            self.assertEqual(lifecycle_contract["source_file_policy"]["source_media_mutation"], "forbidden")
        self.assertEqual(
            contract["repair_reconcile_summary"]["status"],
            "backend_dry_run_and_confirmed_apply_routes_available_startup_dry_run_only",
        )
        self.assertTrue(contract["repair_reconcile_summary"]["mutation_enabled"])
        self.assertTrue(contract["repair_reconcile_summary"]["frontend_allowed"])
        repair_commands = {item["candidate_command"] for item in contract["repair_reconcile_contracts"]}
        self.assertIn("completed.reconcile_manifest", repair_commands)
        self.assertIn("completed.repair_sidecar_metadata", repair_commands)
        self.assertIn("pending_publish.repair_manifest", repair_commands)
        self.assertIn("pending_publish.reconcile_orphan_payloads", repair_commands)
        self.assertIn("startup.reconcile_state", repair_commands)
        for repair_contract in contract["repair_reconcile_contracts"]:
            if repair_contract["candidate_command"] == "startup.reconcile_state":
                self.assertEqual(repair_contract["current_status"], "backend_dry_run_route_available")
                self.assertFalse(repair_contract["mutation_enabled"])
                self.assertNotIn("apply_route", repair_contract)
            else:
                self.assertEqual(
                    repair_contract["current_status"],
                    "backend_dry_run_and_confirmed_apply_routes_available",
                )
                self.assertTrue(repair_contract["mutation_enabled"])
                self.assertIn("apply_route", repair_contract)
            self.assertIn("dry_run_route", repair_contract)
            self.assertEqual(repair_contract["dry_run_contract"]["effect"], "none")
            self.assertIn("dry_run_only", repair_contract["dry_run_contract"]["required_result_fields"])
            self.assertTrue(repair_contract["rollback_contract"]["journal_required"])
            self.assertEqual(repair_contract["source_file_policy"]["source_media_mutation"], "forbidden")
        pipeline_start = next(route for route in contract["routes"] if route["path"] == "/api/pipeline/start")
        self.assertIn("drain_pending_pushes", pipeline_start["allowed_modes"])
        self.assertIn("schedule_override", pipeline_start["request_keys"])
        self.assertEqual(pipeline_start["allowed_schedule_overrides"], ["", "run_once", "ignore"])
        paths_by_effect = {route["path"]: route["effect"] for route in contract["routes"]}
        self.assertEqual(paths_by_effect["/api/rename/preview"], "none")
        self.assertEqual(paths_by_effect["/api/rename/cleaning-filters"], "none")
        self.assertEqual(paths_by_effect["/api/rename/movie-cleaning-filters"], "none")
        self.assertEqual(paths_by_effect["/api/rename/clean-filename-preview"], "none")
        self.assertEqual(paths_by_effect["/api/rename/browse"], "shell-dialog")
        self.assertEqual(paths_by_effect["/api/rename/filter-cases"], "test-fixture-write")
        self.assertEqual(paths_by_effect["/api/rename/apply"], "filesystem-mutation")
        self.assertEqual(paths_by_effect["/api/completed"], "none")
        self.assertEqual(paths_by_effect["/api/completed/open"], "shell-open")
        self.assertEqual(paths_by_effect["/api/completed/reconcile-manifest-dry-run"], "none")
        self.assertEqual(paths_by_effect["/api/completed/repair-sidecar-metadata-dry-run"], "none")
        self.assertEqual(paths_by_effect["/api/failures"], "none")
        self.assertEqual(paths_by_effect["/api/audit-results"], "none")
        self.assertEqual(paths_by_effect["/api/audit-controls"], "none")
        self.assertEqual(paths_by_effect["/api/audit/score-policy"], "audit-state-write")
        self.assertEqual(paths_by_effect["/api/audit/ignore"], "audit-state-write")
        self.assertEqual(paths_by_effect["/api/audit/export-rerun-csv"], "report-file-write")
        self.assertEqual(paths_by_effect["/api/pending-publish"], "none")
        self.assertEqual(paths_by_effect["/api/pending-publish/recovery-plan"], "none")
        self.assertEqual(paths_by_effect["/api/pending-publish/repair-manifest-dry-run"], "none")
        self.assertEqual(paths_by_effect["/api/pending-publish/reconcile-orphan-payloads-dry-run"], "none")
        self.assertEqual(paths_by_effect["/api/startup/reconcile-dry-run"], "none")
        self.assertEqual(paths_by_effect["/api/publish-reconciliation"], "none")
        self.assertEqual(paths_by_effect["/api/maintenance"], "bounded-health-check")
        self.assertEqual(paths_by_effect["/api/maintenance/progress"], "none")
        self.assertEqual(paths_by_effect["/api/maintenance/release-dry-run"], "process-dry-run")
        self.assertEqual(paths_by_effect["/api/maintenance/release-build"], "deployment-write")
        self.assertEqual(paths_by_effect["/api/maintenance/completed-backfill-dry-run"], "process-dry-run")
        self.assertEqual(paths_by_effect["/api/maintenance/dependency-atlas"], "tooling-artifact-write")
        self.assertEqual(paths_by_effect["/api/maintenance/dependency-atlas/open-folder"], "shell-open")
        self.assertEqual(paths_by_effect["/api/schedule"], "none")
        self.assertEqual(paths_by_effect["/api/schedule/preview"], "none")
        self.assertEqual(paths_by_effect["/api/schedule/save"], "app-state-write")
        self.assertEqual(paths_by_effect["/api/network/workers"], "none")
        self.assertEqual(paths_by_effect["/api/network/worker/test-connection"], "none")
        lifecycle_routes = {
            route["path"]: route
            for route in contract["routes"]
            if str(route["path"]).startswith("/api/network/")
            and route.get("network_lifecycle")
        }
        self.assertEqual(
            sorted(lifecycle_routes),
            [
                "/api/network/coordinator/start",
                "/api/network/coordinator/start-dry-run",
                "/api/network/coordinator/stop",
                "/api/network/coordinator/stop-dry-run",
                "/api/network/worker/start",
                "/api/network/worker/start-dry-run",
                "/api/network/worker/stop",
                "/api/network/worker/stop-dry-run",
            ],
        )
        for path, route in lifecycle_routes.items():
            with self.subTest(path=path):
                is_dry_run = path.endswith("-dry-run")
                self.assertEqual(route["owner"], "Network")
                self.assertTrue(route["frontend_exposed"])
                self.assertEqual(route["requires_confirmation"], not is_dry_run)
                self.assertEqual(route["journaled"], not is_dry_run)
                self.assertEqual(route["network_lifecycle"]["role"], "worker" if "/worker/" in path else "coordinator")
                self.assertEqual(route["network_lifecycle"]["action"], "stop" if "/stop" in path else "start")
                self.assertEqual(route["network_lifecycle"]["dry_run"], is_dry_run)
        self.assertEqual(paths_by_effect["/api/diagnostics/open"], "shell-open")
        self.assertEqual(paths_by_effect["/api/diagnostics/tdarr-matrix-audit"], "diagnostic-process")
        self.assertEqual(paths_by_effect["/api/settings/browse-path"], "shell-dialog")
        self.assertEqual(paths_by_effect["/api/settings/preview-patch"], "none")
        self.assertEqual(paths_by_effect["/api/settings/save-patch"], "config-write")
        self.assertEqual(paths_by_effect["/api/settings/reload"], "none")
        self.assertEqual(paths_by_effect["/api/pipeline/control"], "control-flag-write")
        self.assertEqual(paths_by_effect["/api/pipeline/start"], "process-launch")
        self.assertEqual(paths_by_effect["/api/launch/preflight"], "none")
        self.assertEqual(paths_by_effect["/api/backend/close-readiness"], "none")
        self.assertEqual(paths_by_effect["/api/commands"], "none")
        self.assertEqual(paths_by_effect["/api/backend/shutdown"], "backend-lifecycle")
        self.assertEqual(denied_status, 401)
        self.assertEqual(denied["error"], "unauthorized")
        self.assertEqual(snapshot_status, 200)
        self.assertEqual(snapshot["schema_version"], "desktop_app_snapshot.v1")
        self.assertEqual(snapshot["pipeline_state"], "processing")
        self.assertEqual(snapshot["current_work"]["schema_version"], "desktop_current_work.v1")
        self.assertEqual(snapshot["worker_progress"]["schema_version"], "desktop_worker_progress.v1")
        self.assertTrue(snapshot["worker_progress"]["read_only"])
        self.assertEqual(snapshot["ffmpeg_progress"]["schema_version"], "desktop_ffmpeg_progress.v1")
        self.assertTrue(snapshot["ffmpeg_progress"]["read_only"])
        self.assertEqual(snapshot["eta"]["schema_version"], "desktop_eta.v1")
        self.assertTrue(snapshot["eta"]["read_only"])
        self.assertEqual(close_status, 200)
        self.assertEqual(close_readiness["schema_version"], "desktop_close_readiness.v1")
        self.assertFalse(close_readiness["safe_to_close"])
        self.assertEqual(launch_preflight_status, 200)
        self.assertEqual(launch_preflight["schema_version"], "desktop_launch_preflight.v1")
        self.assertEqual(launch_preflight["target"], "pipeline")
        self.assertEqual(launch_preflight["start_route"], "/api/pipeline/start")
        self.assertEqual(launch_preflight["operator_readiness"]["schema_version"], "desktop_launch_readiness.v1")
        self.assertEqual(launch_preflight["operator_readiness"]["evidence_authority"], "backend")
        self.assertEqual(launch_preflight["operator_readiness"]["source_route"], "/api/launch/preflight")
        self.assertTrue(any(row["key"] == "active_work" for row in launch_preflight["checks"]))
        self.assertTrue(any(row["key"] == "encoder_capability_report" for row in launch_preflight["checks"]))
        self.assertEqual(close_readiness["state"], "processing")
        self.assertEqual(telemetry_status, 200)
        self.assertTrue(telemetry["gpu_present"])
        self.assertEqual(telemetry["gpu_encoder_usage"]["schema_version"], "desktop_gpu_encoder_usage.v1")
        self.assertTrue(telemetry["gpu_encoder_usage"]["read_only"])
        self.assertEqual(settings_status, 200)
        self.assertEqual(settings["schema_version"], "desktop_settings_workspace.v1")
        self.assertTrue(any(field["key"] == "RoutingProfile" for field in settings["field_definitions"]))
        self.assertEqual(
            settings["encoder_capability_report"]["schema_version"],
            "settings_encoder_capability_report.v1",
        )
        self.assertTrue(settings["encoder_capability_report"]["read_only"])
        self.assertEqual(settings["profile_summary"]["schema_version"], "desktop_settings_profile_summary.v1")
        self.assertEqual(settings["policy_impact"]["schema_version"], "settings_policy_impact.v1")
        self.assertEqual(settings["policy_impact"]["launch_risk_handoff"]["schema_version"], "settings_launch_risk_handoff.v1")
        self.assertTrue(settings["profile_summary"]["read_only"])
        self.assertFalse(settings["profile_summary"]["webview_profile_operations"]["save_default_profile"])
        self.assertEqual(network_workers_status, 200)
        self.assertEqual(network_workers["schema_version"], "desktop_network_workers.v1")
        self.assertTrue(network_workers["read_only"])
        self.assertEqual(shutdown_status, 200)
        self.assertEqual(shutdown["schema_version"], "desktop_command_result.v1")
        self.assertEqual(shutdown["command"], "backend.shutdown")
        self.assertFalse(shutdown["ok"])
        self.assertEqual(shutdown["severity"], "error")
        self.assertEqual(shutdown["message"], "Backend shutdown blocked because active work may still be running.")
        self.assertEqual(shutdown["data"]["safe_to_close"], False)
        self.assertEqual(shutdown["data"]["state"], "processing")
        self.assertFalse(shutdown_event.wait(0.2))

    def test_local_api_shutdown_blocks_when_active_jobs_block_close(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            resolved = _resolved(root)
            idle_snapshot = Snapshot(
                resolved=resolved,
                current_activity="Ready.",
                status_summary="Idle",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Completed", "CurrentStage": "completed"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )
            service.snapshot = idle_snapshot
            active_jobs = resolved.active_jobs_path
            active_jobs.mkdir(parents=True, exist_ok=True)
            (active_jobs / "launching.json").write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_active_job.v1",
                        "launch_id": "launching",
                        "job_kind": "pipeline",
                        "mode": "continuous",
                        "status": "launching",
                        "pid": None,
                        "app_pid": 1234,
                        "command_line": "pwsh -File MediaPipeline.ps1",
                        "args": ["pwsh", "-File", "MediaPipeline.ps1"],
                        "cwd": str(root),
                        "stdout_log": "",
                        "stderr_log": "",
                        "show_console": False,
                        "metadata": {},
                        "launched_at": "2026-05-08T21:00:00-04:00",
                        "last_update": "2026-05-08T21:00:01-04:00",
                        "return_code": None,
                    }
                ),
                encoding="utf-8",
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            shutdown_event = threading.Event()
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
                snapshot_provider=lambda: idle_snapshot,
                audit_root_provider=lambda: str(root),
                shutdown_request=shutdown_event.set,
            )
            try:
                server.start()
                readiness_status, readiness = self._get_json(f"{server.url}/api/backend/close-readiness", token="test-token")
                denied_status, denied = self._post_json(f"{server.url}/api/backend/shutdown", {"reason": "test"})
                shutdown_status, shutdown = self._post_json(
                    f"{server.url}/api/backend/shutdown",
                    {"reason": "test"},
                    token="test-token",
                )
            finally:
                server.stop()

        self.assertEqual(readiness_status, 200)
        self.assertFalse(readiness["safe_to_close"])
        self.assertIn("ActiveJobs still reports active work", readiness["reason"])
        self.assertEqual(denied_status, 401)
        self.assertEqual(denied["error"], "unauthorized")
        self.assertEqual(shutdown_status, 200)
        self.assertEqual(shutdown["command"], "backend.shutdown")
        self.assertFalse(shutdown["ok"])
        self.assertEqual(shutdown["severity"], "error")
        self.assertEqual(shutdown["message"], "Backend shutdown blocked because active work may still be running.")
        self.assertEqual(shutdown["data"]["safe_to_close"], False)
        self.assertEqual(shutdown["data"]["state"], "completed")
        self.assertIn("ActiveJobs still reports active work", shutdown["errors"][0])
        self.assertFalse(shutdown_event.wait(0.2))

    def test_local_api_shutdown_blocks_when_schedule_stop_watcher_is_armed(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyWorkflowFacadeService(root)
            resolved = _resolved(root)
            service.find_related_pipeline_processes = lambda _resolved_arg: []  # type: ignore[method-assign]
            service.read_progress = lambda _resolved_arg: {}  # type: ignore[method-assign]
            service.is_progress_stale = lambda _progress: True  # type: ignore[method-assign]
            service.read_audit_progress = lambda _resolved_arg: {}  # type: ignore[method-assign]
            service.is_audit_progress_stale = lambda _progress: True  # type: ignore[method-assign]
            idle_snapshot = Snapshot(
                resolved=resolved,
                current_activity="Ready.",
                status_summary="Idle",
                log_tail="",
                progress={"ProgressVersion": 2, "Status": "Completed", "CurrentStage": "completed"},
                audit_progress=None,
                latest_failure_report=None,
                latest_failure_json=None,
                latest_audit_csv=None,
                latest_priority_csv=None,
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            deadline = (datetime.now() + timedelta(seconds=30)).replace(microsecond=0)
            facade._schedule_stop_watcher.arm(  # type: ignore[attr-defined]
                service=service,
                resolved=resolved,
                proc=DummyProc(7777),
                deadline=deadline,
            )
            shutdown_event = threading.Event()
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
                snapshot_provider=lambda: idle_snapshot,
                audit_root_provider=lambda: str(root),
                shutdown_request=shutdown_event.set,
            )
            try:
                server.start()
                readiness_status, readiness = self._get_json(f"{server.url}/api/backend/close-readiness", token="test-token")
                shutdown_status, shutdown = self._post_json(
                    f"{server.url}/api/backend/shutdown",
                    {"reason": "test"},
                    token="test-token",
                )
            finally:
                server.stop()

        self.assertEqual(readiness_status, 200)
        self.assertFalse(readiness["safe_to_close"])
        self.assertEqual(readiness["state"], "completed")
        self.assertIn("schedule-stop watcher is armed", readiness["reason"])
        self.assertIn("PID 7777", readiness["reason"])
        self.assertEqual(readiness["continuous_watcher"]["status"], "armed")
        self.assertEqual(readiness["continuous_watcher"]["pid"], 7777)
        self.assertGreater(readiness["continuous_watcher"]["generation"], 0)
        self.assertEqual(shutdown_status, 200)
        self.assertEqual(shutdown["command"], "backend.shutdown")
        self.assertFalse(shutdown["ok"])
        self.assertEqual(shutdown["severity"], "error")
        self.assertEqual(shutdown["message"], "Backend shutdown blocked because active work may still be running.")
        self.assertFalse(shutdown["data"]["safe_to_close"])
        self.assertEqual(shutdown["data"]["state"], "completed")
        self.assertEqual(shutdown["data"]["reason"], readiness["reason"])
        self.assertEqual(shutdown["data"]["continuous_watcher"]["status"], "armed")
        self.assertEqual(shutdown["data"]["continuous_watcher"]["pid"], 7777)
        self.assertEqual(
            shutdown["data"]["continuous_watcher"]["generation"],
            readiness["continuous_watcher"]["generation"],
        )
        self.assertIn("schedule-stop watcher is armed", shutdown["errors"][0])
        self.assertFalse(shutdown_event.wait(0.2))

    def test_local_api_shutdown_force_cleanup_invokes_backend_owned_process_cleanup(self) -> None:
        shutdown_event = threading.Event()
        logger_name = "test.local_api.force_shutdown_cleanup"
        cleanup_calls: list[str] = []
        resolved = object()

        class Readiness:
            def to_mapping(self) -> dict[str, object]:
                return {
                    "schema_version": "desktop_close_readiness.v1",
                    "safe_to_close": False,
                    "state": "processing",
                    "active_work": True,
                    "reason": "Active pipeline process is running.",
                    "continuous_watcher": {},
                }

        class CleanupService:
            def kill_active_spawned_processes(self) -> list[str]:
                cleanup_calls.append("tracked")
                return ["Force-killed tracked pipeline process tree (PID 1234)."]

            def kill_related_pipeline_processes(self, value: object) -> list[str]:
                self.related_resolved = value
                cleanup_calls.append("related")
                return []

        class CleanupFacade:
            service = CleanupService()

            def get_close_readiness(self, _resolved: object, _snapshot: object) -> Readiness:
                return Readiness()

        class Harness(LocalApiProcessCommandPayloadMixin):
            shutdown_request = shutdown_event.set
            facade = CleanupFacade()
            logger = logging.getLogger(logger_name)

            def _resolved(self) -> object:
                return resolved

            def _snapshot(self) -> None:
                return None

        payload = Harness()._backend_shutdown_payload({"force_active_work_shutdown": True})

        self.assertEqual(cleanup_calls, ["tracked", "related"])
        self.assertTrue(shutdown_event.wait(1.0))
        self.assertEqual(payload["command"], "backend.shutdown")
        self.assertEqual(payload["severity"], "warning")
        self.assertEqual(payload["message"], "Backend shutdown requested with forced active-work cleanup.")
        self.assertTrue(payload["data"]["forced_active_work_shutdown"])
        self.assertEqual(payload["data"]["cleanup_messages"], ["Force-killed tracked pipeline process tree (PID 1234)."])
        self.assertIn("Active pipeline process is running.", payload["warnings"][0])
        self.assertIn("Force-killed tracked pipeline", payload["warnings"][1])

    def test_local_api_shutdown_force_cleanup_ignores_non_boolean_truthy_values(self) -> None:
        shutdown_event = threading.Event()
        cleanup_calls: list[str] = []
        resolved = object()

        class Readiness:
            def to_mapping(self) -> dict[str, object]:
                return {
                    "schema_version": "desktop_close_readiness.v1",
                    "safe_to_close": False,
                    "state": "processing",
                    "active_work": True,
                    "reason": "Active pipeline process is running.",
                    "continuous_watcher": {},
                }

        class CleanupService:
            def kill_active_spawned_processes(self) -> list[str]:
                cleanup_calls.append("tracked")
                return ["Force-killed tracked pipeline process tree (PID 1234)."]

            def kill_related_pipeline_processes(self, _resolved: object) -> list[str]:
                cleanup_calls.append("related")
                return []

        class CleanupFacade:
            service = CleanupService()

            def get_close_readiness(self, _resolved: object, _snapshot: object) -> Readiness:
                return Readiness()

        class Harness(LocalApiProcessCommandPayloadMixin):
            shutdown_request = shutdown_event.set
            facade = CleanupFacade()
            logger = logging.getLogger("test.local_api.force_shutdown_type_guard")

            def _resolved(self) -> object:
                return resolved

            def _snapshot(self) -> None:
                return None

        payload = Harness()._backend_shutdown_payload({"force_active_work_shutdown": "true"})

        self.assertEqual(cleanup_calls, [])
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["severity"], "error")
        self.assertEqual(payload["message"], "Backend shutdown blocked because active work may still be running.")
        self.assertFalse(shutdown_event.wait(0.2))

    def test_local_api_shutdown_logs_close_readiness_exceptions(self) -> None:
        shutdown_event = threading.Event()
        logger_name = "test.local_api.shutdown"

        class RaisingFacade:
            def get_close_readiness(self, _resolved: object, _snapshot: object) -> object:
                raise RuntimeError("progress unreadable")

        class Harness(LocalApiProcessCommandPayloadMixin):
            shutdown_request = shutdown_event.set
            facade = RaisingFacade()
            logger = logging.getLogger(logger_name)

            def _resolved(self) -> object:
                return object()

            def _snapshot(self) -> None:
                return None

        with self.assertLogs(logger_name, level="ERROR") as logs:
            payload = Harness()._backend_shutdown_payload({})

        self.assertEqual(payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(payload["command"], "backend.shutdown")
        self.assertFalse(payload["ok"])
        self.assertEqual(payload["severity"], "error")
        self.assertEqual(payload["message"], "Backend shutdown blocked because active work may still be running.")
        self.assertFalse(payload["data"]["safe_to_close"])
        self.assertEqual(payload["data"]["state"], "unknown")
        self.assertIn("Close readiness could not be verified", payload["errors"][0])
        self.assertIn("local API close-readiness verification failed", "\n".join(logs.output))
        self.assertFalse(shutdown_event.wait(0.2))

    def test_local_api_shutdown_logs_callback_failures_after_response(self) -> None:
        callback_event = threading.Event()
        log_event = threading.Event()
        records: list[logging.LogRecord] = []
        logger_name = "test.local_api.shutdown_callback"
        logger = logging.getLogger(logger_name)

        class EventHandler(logging.Handler):
            def emit(self, record: logging.LogRecord) -> None:
                records.append(record)
                log_event.set()

        class Harness(LocalApiProcessCommandPayloadMixin):
            facade = object()
            logger = logging.getLogger(logger_name)

            def shutdown_request(self) -> None:
                callback_event.set()
                raise RuntimeError("shutdown callback broke")

        handler = EventHandler(level=logging.ERROR)
        old_level = logger.level
        logger.addHandler(handler)
        logger.setLevel(logging.ERROR)
        try:
            Harness()._request_backend_shutdown_after_response()
            self.assertTrue(callback_event.wait(1.0))
            self.assertTrue(log_event.wait(1.0))
        finally:
            logger.removeHandler(handler)
            logger.setLevel(old_level)

        combined = "\n".join(record.getMessage() for record in records)
        self.assertIn("local API backend shutdown callback failed", combined)
        self.assertTrue(any(record.exc_info for record in records))

    def test_local_api_shutdown_logs_timer_start_failures(self) -> None:
        logger_name = "test.local_api.shutdown_timer"

        class BrokenTimer:
            daemon = False

            def __init__(self, *_args, **_kwargs) -> None:
                pass

            def start(self) -> None:
                raise RuntimeError("timer unavailable")

        class Harness(LocalApiProcessCommandPayloadMixin):
            facade = object()
            logger = logging.getLogger(logger_name)
            shutdown_request = lambda self: None

        with (
            patch("mediapipeline.core.api.commands_process.threading.Timer", BrokenTimer),
            self.assertLogs(logger_name, level="ERROR") as logs,
        ):
            Harness()._request_backend_shutdown_after_response()

        self.assertIn("local API backend shutdown timer start failed", "\n".join(logs.output))

    def test_local_api_queue_state_routes_are_contracted_journaled_and_source_scoped(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_movie = root / "Movies" / "Movie.mkv"
            source_tv = root / "TV" / "Show" / "Show S01E01.mkv"
            outside = root / "Other" / "Outside.mkv"
            source_movie.parent.mkdir(parents=True, exist_ok=True)
            source_tv.parent.mkdir(parents=True, exist_ok=True)
            outside.parent.mkdir(parents=True, exist_ok=True)
            source_movie.write_bytes(b"movie")
            source_tv.write_bytes(b"tv")
            outside.write_bytes(b"outside")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.priority_manifest_path = resolved.state_root / "priority_manifest.json"
            resolved.queue_strategy_path = resolved.state_root / "queue_strategy.json"
            resolved.file_overrides_path = resolved.state_root / "file_overrides.json"
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-state-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                strategy_status, strategy = self._get_json(f"{server.url}/api/queue/strategy", token=server.token)
                invalid_status, invalid_priority = self._post_json(
                    f"{server.url}/api/queue/priority",
                    {"path": str(outside), "level": "high"},
                    token=server.token,
                )
                priority_status, priority = self._post_json(
                    f"{server.url}/api/queue/priority",
                    {"path": str(source_movie), "level": "high", "reason": "test"},
                    token=server.token,
                )
                override_invalid_status, override_invalid = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(outside), "audio": {"maxChannels": 2}},
                    token=server.token,
                )
                override_status, override = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source_tv), "audio": {"maxChannels": 2}},
                    token=server.token,
                )
                override_read_status, override_read = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source_tv))}",
                    token=server.token,
                )
                strategy_save_status, strategy_save = self._post_json(
                    f"{server.url}/api/queue/strategy",
                    {"strategy": "FreshestFirst"},
                    token=server.token,
                )
                commands_status, commands = self._get_json(f"{server.url}/api/commands?limit=10", token=server.token)
            finally:
                server.stop()

        self.assertEqual(strategy_status, 200)
        self.assertTrue(strategy["ok"])
        self.assertEqual(invalid_status, 200)
        self.assertFalse(invalid_priority["ok"])
        self.assertEqual(invalid_priority["schema_version"], "desktop_command_result.v1")
        self.assertIn("outside configured source roots", invalid_priority["errors"][0])
        self.assertEqual(priority_status, 200)
        self.assertTrue(priority["ok"])
        self.assertEqual(priority["schema_version"], "desktop_command_result.v1")
        self.assertEqual(priority["entry_count"], 1)
        self.assertEqual(override_invalid_status, 200)
        self.assertFalse(override_invalid["ok"])
        self.assertEqual(override_invalid["schema_version"], "desktop_command_result.v1")
        self.assertIn("outside configured source roots", override_invalid["errors"][0])
        self.assertEqual(override_status, 200)
        self.assertTrue(override["ok"])
        self.assertEqual(override["schema_version"], "desktop_command_result.v1")
        self.assertEqual(override["entry_count"], 1)
        self.assertEqual(override_read_status, 200)
        self.assertTrue(override_read["has_override"])
        self.assertEqual(override_read["path"], str(source_tv))
        self.assertEqual(strategy_save_status, 200)
        self.assertTrue(strategy_save["ok"])
        self.assertEqual(strategy_save["schema_version"], "desktop_command_result.v1")
        self.assertEqual(commands_status, 200)
        journaled = {entry["command"] for entry in commands["entries"]}
        self.assertIn("queue.priority", journaled)
        self.assertIn("queue.file_overrides", journaled)
        self.assertIn("queue.strategy", journaled)

    def test_local_api_queue_priority_clear_all_clears_entire_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_movie = root / "Movies" / "Movie.mkv"
            source_tv = root / "TV" / "Show" / "Show S01E01.mkv"
            source_movie.parent.mkdir(parents=True, exist_ok=True)
            source_tv.parent.mkdir(parents=True, exist_ok=True)
            source_movie.write_bytes(b"movie")
            source_tv.write_bytes(b"tv")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.priority_manifest_path = resolved.state_root / "priority_manifest.json"
            resolved.priority_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            resolved.priority_manifest_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": {
                            str(source_movie).replace("\\", "/").lower(): {
                                "level": "high",
                                "reason": "visible row",
                                "set_at": "2026-06-02T00:00:00+00:00",
                            },
                            str(source_tv).replace("\\", "/").lower(): {
                                "level": "hold",
                                "reason": "not currently visible",
                                "set_at": "2026-06-02T00:00:00+00:00",
                            },
                        },
                    }
                ),
                encoding="utf-8",
            )
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-priority-clear-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                clear_status, clear_payload = self._post_json(
                    f"{server.url}/api/queue/priority",
                    {"clear_all": True},
                    token=server.token,
                )
                read_status, read_payload = self._get_json(
                    f"{server.url}/api/queue/priority",
                    token=server.token,
                )
            finally:
                server.stop()

        self.assertEqual(clear_status, 200)
        self.assertTrue(clear_payload["ok"])
        self.assertEqual(clear_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(clear_payload["entry_count"], 0)
        self.assertIn("All priority manifest entries cleared", clear_payload["message"])
        self.assertEqual(read_status, 200)
        self.assertEqual(read_payload["entry_count"], 0)
        self.assertEqual(read_payload["entries"], {})

    def test_local_api_queue_priority_read_fails_closed_when_manifest_is_corrupt(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.priority_manifest_path = resolved.state_root / "priority_manifest.json"
            resolved.priority_manifest_path.parent.mkdir(parents=True, exist_ok=True)
            resolved.priority_manifest_path.write_text("{not-json", encoding="utf-8")
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-priority-corrupt-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                read_status, read_payload = self._get_json(
                    f"{server.url}/api/queue/priority",
                    token=server.token,
                )
                clear_status, clear_payload = self._post_json(
                    f"{server.url}/api/queue/priority",
                    {"clear_all": True},
                    token=server.token,
                )
            finally:
                server.stop()

        self.assertEqual(read_status, 200)
        self.assertFalse(read_payload["ok"])
        self.assertEqual(read_payload["schema_version"], "desktop_command_result.v1")
        self.assertIn("Priority manifest is unreadable", read_payload["errors"][0])
        self.assertEqual(clear_status, 200)
        self.assertTrue(clear_payload["ok"])
        self.assertEqual(clear_payload["entry_count"], 0)

    def test_local_api_queue_priority_bulk_accepts_manual_order_positions(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source_movie = root / "Movies" / "Movie.mkv"
            source_tv = root / "TV" / "Show" / "Show S01E01.mkv"
            source_movie.parent.mkdir(parents=True, exist_ok=True)
            source_tv.parent.mkdir(parents=True, exist_ok=True)
            source_movie.write_bytes(b"movie")
            source_tv.write_bytes(b"tv")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.priority_manifest_path = resolved.state_root / "priority_manifest.json"
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-manual-position-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                position_status, position_payload = self._post_json(
                    f"{server.url}/api/queue/priority",
                    {
                        "items": [
                            {"path": str(source_movie), "level": "normal", "position": 2},
                            {"path": str(source_tv), "level": "normal", "position": 1},
                        ],
                    },
                    token=server.token,
                )
                read_status, read_payload = self._get_json(
                    f"{server.url}/api/queue/priority",
                    token=server.token,
                )
            finally:
                server.stop()

        movie_key = str(source_movie).replace("\\", "/").lower()
        tv_key = str(source_tv).replace("\\", "/").lower()
        self.assertEqual(position_status, 200)
        self.assertTrue(position_payload["ok"])
        self.assertEqual(read_status, 200)
        self.assertEqual(read_payload["entries"][movie_key]["position"], 2.0)
        self.assertEqual(read_payload["entries"][tv_key]["position"], 1.0)
        self.assertEqual(read_payload["entries"][movie_key]["level"], "normal")

    def test_local_api_file_override_clear_fields_preserves_save_and_full_clear(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "TV" / "Show" / "Show S01E01.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"media")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.file_overrides_path = resolved.state_root / "file_overrides.json"
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-clear-fields-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                save_status, save = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "audio": {
                            "keepTracks": [{"language": "eng"}],
                            "maxChannels": 6,
                        },
                        "subtitles": {
                            "keepTracks": [{"language": "eng"}],
                            "stripAll": True,
                        },
                    },
                    token=server.token,
                )
                clear_status, clear = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "clear_fields": ["audio.maxChannels", "subtitles.stripAll"],
                    },
                    token=server.token,
                )
                unknown_status, unknown = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "clear_fields": ["audio.loudnessMode"]},
                    token=server.token,
                )
                read_status, read_payload = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
                full_clear_status, full_clear = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "clear": True},
                    token=server.token,
                )
                read_cleared_status, read_cleared = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
                save_again_status, save_again = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"maxChannels": 2}},
                    token=server.token,
                )
                read_saved_status, read_saved = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
            finally:
                server.stop()

        self.assertEqual(save_status, 200)
        self.assertTrue(save["ok"])
        self.assertEqual(clear_status, 200)
        self.assertTrue(clear["ok"])
        self.assertEqual(clear["entry_count"], 1)
        self.assertEqual(unknown_status, 200)
        self.assertFalse(unknown["ok"])
        self.assertEqual(unknown["schema_version"], "desktop_command_result.v1")
        self.assertIn("Unsupported clear_fields path", unknown["message"])
        self.assertEqual(read_status, 200)
        self.assertTrue(read_payload["has_override"])
        entry = read_payload["entry"]
        self.assertEqual(entry["audio"], {"keepTracks": [{"language": "eng"}]})
        self.assertEqual(entry["subtitles"], {"keepTracks": [{"language": "eng"}]})
        self.assertEqual(full_clear_status, 200)
        self.assertTrue(full_clear["ok"])
        self.assertEqual(read_cleared_status, 200)
        self.assertFalse(read_cleared["has_override"])
        self.assertEqual(save_again_status, 200)
        self.assertTrue(save_again["ok"])
        self.assertEqual(read_saved_status, 200)
        self.assertEqual(read_saved["entry"]["audio"], {"maxChannels": 2})

    def test_local_api_file_override_validates_current_payload_fields(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "TV" / "Show" / "Show S01E01.mkv"
            strip_true_source = root / "TV" / "Show" / "Show S01E02.mkv"
            strip_false_source = root / "TV" / "Show" / "Show S01E03.mkv"
            for path in (source, strip_true_source, strip_false_source):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"media")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.file_overrides_path = resolved.state_root / "file_overrides.json"
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-override-validation-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                valid_status, valid = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "audio": {
                            "keepTracks": [{"language": "eng"}],
                            "dropTracks": [{"language": "jpn"}],
                            "renameTracks": [{"language": "eng", "channels": 6, "newTitle": "English 5.1"}],
                            "maxChannels": 6,
                            "downmixMode": "max_channels",
                            "transcodeCodec": "eac3",
                            "transcodeBitrate": "640k",
                            "preferDefaultLanguage": "eng",
                        },
                        "subtitles": {
                            "keepTracks": [{"language": "eng"}],
                            "dropTracks": [{"language": "und"}],
                            "stripAll": False,
                        },
                    },
                    token=server.token,
                )
                read_status, read_payload = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
                max_channel_results = []
                for max_channels in (2, 6, 8):
                    max_channel_results.append(
                        self._post_json(
                            f"{server.url}/api/queue/file-overrides",
                            {"path": str(source), "audio": {"maxChannels": max_channels}},
                            token=server.token,
                        )
                    )
                strip_true_status, strip_true = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(strip_true_source), "subtitles": {"stripAll": True}},
                    token=server.token,
                )
                strip_false_status, strip_false = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(strip_false_source), "subtitles": {"stripAll": False}},
                    token=server.token,
                )
                invalid_string_status, invalid_string = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"maxChannels": "6"}},
                    token=server.token,
                )
                invalid_zero_status, invalid_zero = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"maxChannels": 0}},
                    token=server.token,
                )
                invalid_negative_status, invalid_negative = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"maxChannels": -1}},
                    token=server.token,
                )
                invalid_top_status, invalid_top = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"maxChannels": 2}, "route": "encode"},
                    token=server.token,
                )
                invalid_nested_status, invalid_nested = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"loudnessMode": "night"}},
                    token=server.token,
                )
                invalid_selector_status, invalid_selector = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"keepTracks": [{"language": 5}]}},
                    token=server.token,
                )
                invalid_safe_field_status, invalid_safe_field = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"preferDefaultLanguage": 5}},
                    token=server.token,
                )
                invalid_deferred_enum_status, invalid_deferred_enum = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"downmixMode": "invalid"}},
                    token=server.token,
                )
                invalid_deferred_bitrate_status, invalid_deferred_bitrate = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "audio": {"transcodeBitrate": "not-a-bitrate"}},
                    token=server.token,
                )
                invalid_clear_status, invalid_clear = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "clear_fields": ["subtitles.renameTracks"]},
                    token=server.token,
                )
                clear_all_status, clear_all = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"clear_all": True},
                    token=server.token,
                )
                manifest_status, manifest = self._get_json(
                    f"{server.url}/api/queue/file-overrides",
                    token=server.token,
                )
            finally:
                server.stop()

        self.assertEqual(valid_status, 200)
        self.assertTrue(valid["ok"])
        self.assertEqual(read_status, 200)
        entry = read_payload["entry"]
        self.assertEqual(entry["audio"]["keepTracks"], [{"language": "eng"}])
        self.assertEqual(entry["audio"]["dropTracks"], [{"language": "jpn"}])
        self.assertEqual(entry["audio"]["renameTracks"], [{"language": "eng", "channels": 6, "newTitle": "English 5.1"}])
        self.assertEqual(entry["audio"]["maxChannels"], 6)
        self.assertEqual(entry["audio"]["downmixMode"], "max_channels")
        self.assertEqual(entry["audio"]["transcodeCodec"], "eac3")
        self.assertEqual(entry["audio"]["transcodeBitrate"], "640k")
        self.assertEqual(entry["audio"]["preferDefaultLanguage"], "eng")
        self.assertEqual(entry["subtitles"]["keepTracks"], [{"language": "eng"}])
        self.assertEqual(entry["subtitles"]["dropTracks"], [{"language": "und"}])
        self.assertFalse(entry["subtitles"]["stripAll"])
        for status, payload in max_channel_results:
            self.assertEqual(status, 200)
            self.assertTrue(payload["ok"])
        self.assertEqual(strip_true_status, 200)
        self.assertTrue(strip_true["ok"])
        self.assertEqual(strip_false_status, 200)
        self.assertTrue(strip_false["ok"])
        for status, payload, expected in [
            (invalid_string_status, invalid_string, "'audio.maxChannels' must be an integer."),
            (invalid_zero_status, invalid_zero, "'audio.maxChannels' must be one of: 2, 6, 8."),
            (invalid_negative_status, invalid_negative, "'audio.maxChannels' must be one of: 2, 6, 8."),
            (invalid_top_status, invalid_top, "Unsupported file override request field(s): route"),
            (invalid_nested_status, invalid_nested, "Unsupported audio field(s): loudnessMode"),
            (invalid_selector_status, invalid_selector, "'audio.keepTracks[0].language' must be a string."),
            (invalid_safe_field_status, invalid_safe_field, "'audio.preferDefaultLanguage' must be a string."),
            (invalid_deferred_enum_status, invalid_deferred_enum, "'audio.downmixMode' must be one of:"),
            (invalid_deferred_bitrate_status, invalid_deferred_bitrate, "'audio.transcodeBitrate' must match"),
            (invalid_clear_status, invalid_clear, "Unsupported clear_fields path(s): subtitles.renameTracks"),
        ]:
            with self.subTest(expected=expected):
                self.assertEqual(status, 200)
                self.assertFalse(payload["ok"])
                self.assertEqual(payload["schema_version"], "desktop_command_result.v1")
                self.assertIn(expected, "\n".join(payload.get("errors", [])))
        self.assertEqual(clear_all_status, 200)
        self.assertTrue(clear_all["ok"])
        self.assertEqual(manifest_status, 200)
        self.assertTrue(manifest["ok"])
        self.assertEqual(manifest["entry_count"], 0)

    def test_local_api_file_override_effective_read_reports_match_sources_and_library_defaults(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            tv_root = root / "Anime"
            legacy_tv_root = root / "TV"
            movies_root = root / "Movies"
            source = tv_root / "Show" / "Season 01" / "Show S01E01.mkv"
            source_no_override = tv_root / "Show" / "Season 01" / "Show S01E02.mkv"
            folder_source = tv_root / "Folder" / "Folder Episode.mkv"
            outside = root / "Other" / "Outside.mkv"
            for path in (source, source_no_override, folder_source, outside):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"media")
            movies_root.mkdir(parents=True, exist_ok=True)
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = movies_root
            resolved.source_tv = legacy_tv_root
            resolved.file_overrides_path = resolved.state_root / "file_overrides.json"
            resolved.config_data = {
                "SourceMovies": str(movies_root),
                "SourceTV": str(legacy_tv_root),
                "PreferredDefaultAudioLanguages": ["jpn"],
                "AudioMaxChannels": 8,
                "SubKeepLanguages": ["spa"],
                "LibraryProfiles": [
                    {
                        "id": "anime",
                        "name": "Anime",
                        "enabled": True,
                        "designation": "tv",
                        "source_path": str(tv_root),
                        "overrides": {
                            "audio": {
                                "PreferredDefaultAudioLanguages": ["eng"],
                                "AudioMaxChannels": 6,
                            },
                            "subtitles": {"SubKeepLanguages": ["eng"]},
                        },
                    }
                ],
            }
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-effective-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                missing_status, missing = self._get_json(
                    f"{server.url}/api/queue/file-overrides/effective",
                    token=server.token,
                )
                invalid_status, invalid = self._get_json(
                    f"{server.url}/api/queue/file-overrides/effective?path={quote(str(outside))}",
                    token=server.token,
                )
                no_override_status, no_override = self._get_json(
                    f"{server.url}/api/queue/file-overrides/effective?path={quote(str(source_no_override))}",
                    token=server.token,
                )
                self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "audio": {
                            "keepTracks": [{"language": "jpn"}],
                            "preferDefaultLanguage": "jpn",
                        },
                        "subtitles": {"stripAll": False},
                    },
                    token=server.token,
                )
                exact_status, exact = self._get_json(
                    f"{server.url}/api/queue/file-overrides/effective?path={quote(str(source))}",
                    token=server.token,
                )
                manifest_before = resolved.file_overrides_path.read_text(encoding="utf-8")
                repeat_status, repeat = self._get_json(
                    f"{server.url}/api/queue/file-overrides/effective?path={quote(str(source))}",
                    token=server.token,
                )
                manifest_after = resolved.file_overrides_path.read_text(encoding="utf-8")
                self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(folder_source.parent),
                        "audio": {"preferDefaultLanguage": "spa"},
                        "subtitles": {"dropTracks": [{"language": "und"}]},
                    },
                    token=server.token,
                )
                folder_status, folder = self._get_json(
                    f"{server.url}/api/queue/file-overrides/effective?path={quote(str(folder_source))}",
                    token=server.token,
                )
            finally:
                server.stop()

        self.assertEqual(missing_status, 200)
        self.assertFalse(missing["ok"])
        self.assertIn("'path' is required", missing["message"])
        self.assertEqual(invalid_status, 200)
        self.assertFalse(invalid["ok"])
        self.assertIn("outside configured source roots", invalid["message"])
        self.assertEqual(no_override_status, 200)
        self.assertTrue(no_override["ok"])
        self.assertFalse(no_override["has_file_override"])
        self.assertEqual(no_override["library"]["name"], "Anime")
        self.assertEqual(no_override["inherited"]["audioKeepLanguages"]["display"], "eng")
        self.assertEqual(no_override["inherited"]["audioMaxChannels"]["display"], "6 channels")
        self.assertEqual(no_override["inherited"]["subtitleKeepLanguages"]["display"], "eng")
        self.assertFalse(no_override["inherited"]["audioDropLanguages"]["available"])
        self.assertEqual(no_override["sources"]["audio.maxChannels"], "library")
        self.assertEqual(no_override["sources"]["audio.preferDefaultLanguage"], "library")
        self.assertIn("resolved_track_actions", no_override)
        self.assertIn("audio", no_override["resolved_track_actions"])
        self.assertIn("subtitles", no_override["resolved_track_actions"])
        self.assertIn("track_selection_preview", no_override)
        no_override_prefer = no_override["expanded_effective_fields"]["audioPreferDefaultLanguage"]
        self.assertEqual(no_override_prefer["field_path"], "audio.preferDefaultLanguage")
        self.assertTrue(no_override_prefer["available"])
        self.assertEqual(no_override_prefer["display"], "eng")
        self.assertEqual(no_override_prefer["source"], "library")
        self.assertEqual(no_override_prefer["source_key"], "PreferredDefaultAudioLanguages")
        self.assertFalse(no_override_prefer["can_clear_file_field"])
        self.assertEqual(no_override_prefer["inherited"]["display"], "eng")
        self.assertEqual(no_override_prefer["effective"]["source"], "library")
        self.assertEqual(exact_status, 200)
        self.assertTrue(exact["has_file_override"])
        self.assertEqual(exact["file_override_scope"], "file")
        self.assertEqual(exact["sources"]["audio.keepTracks"], "file_override")
        self.assertEqual(exact["sources"]["audio.preferDefaultLanguage"], "file_override")
        self.assertEqual(exact["sources"]["subtitles.stripAll"], "file_override")
        self.assertFalse(exact["effective_drawer_fields"]["subtitleStripAll"]["value"])
        self.assertEqual(exact["effective_drawer_fields"]["audioMaxChannels"]["source"], "library")
        exact_prefer = exact["expanded_effective_fields"]["audioPreferDefaultLanguage"]
        self.assertEqual(exact_prefer["display"], "jpn")
        self.assertEqual(exact_prefer["source"], "file_override")
        self.assertEqual(exact_prefer["source_key"], "audio.preferDefaultLanguage")
        self.assertTrue(exact_prefer["can_clear_file_field"])
        self.assertEqual(exact_prefer["inherited"]["display"], "eng")
        self.assertEqual(exact_prefer["effective"]["can_clear_file_field"], True)
        self.assertEqual(repeat_status, 200)
        self.assertTrue(repeat["ok"])
        self.assertEqual(manifest_after, manifest_before)
        self.assertEqual(folder_status, 200)
        self.assertTrue(folder["has_file_override"])
        self.assertEqual(folder["file_override_scope"], "folder")
        self.assertEqual(folder["sources"]["subtitles.dropTracks"], "folder_override")
        self.assertEqual(folder["sources"]["audio.preferDefaultLanguage"], "folder_override")
        folder_prefer = folder["expanded_effective_fields"]["audioPreferDefaultLanguage"]
        self.assertEqual(folder_prefer["display"], "spa")
        self.assertEqual(folder_prefer["source"], "folder_override")
        self.assertFalse(folder_prefer["can_clear_file_field"])

    def test_local_api_file_override_revalidates_merged_route_video_edits(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "TV" / "Show" / "Show S01E01.mkv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"media")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.file_overrides_path = resolved.state_root / "file_overrides.json"
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-merged-override-validation-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                video_status, video = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "video": {
                            "codec": "h264_nvenc",
                            "container": "mp4",
                        },
                    },
                    token=server.token,
                )
                remux_status, remux = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "routing": {"profile": "remux"},
                    },
                    token=server.token,
                )
                read_after_reject_status, read_after_reject = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
                transcode_status, transcode = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "routing": {"profile": "transcode"},
                    },
                    token=server.token,
                )
                threshold_status, threshold = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "routing": {"routeThresholdMode": "bitrate"},
                    },
                    token=server.token,
                )
                audio_status, audio = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "audio": {"maxChannels": 6},
                    },
                    token=server.token,
                )
                read_after_valid_status, read_after_valid = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
            finally:
                server.stop()

        self.assertEqual(video_status, 200)
        self.assertTrue(video["ok"])
        self.assertEqual(remux_status, 200)
        self.assertFalse(remux["ok"])
        self.assertEqual(remux["message"], "Invalid file override payload.")
        self.assertIn("cannot be combined", "\n".join(remux.get("errors", [])))
        self.assertEqual(read_after_reject_status, 200)
        rejected_entry = read_after_reject["entry"]
        self.assertEqual(rejected_entry["video"], {"codec": "h264_nvenc", "container": "mp4"})
        self.assertNotIn("routing", rejected_entry)
        self.assertEqual(transcode_status, 200)
        self.assertTrue(transcode["ok"])
        self.assertEqual(threshold_status, 200)
        self.assertTrue(threshold["ok"])
        self.assertEqual(audio_status, 200)
        self.assertTrue(audio["ok"])
        self.assertEqual(read_after_valid_status, 200)
        valid_entry = read_after_valid["entry"]
        self.assertEqual(valid_entry["video"], {"codec": "h264_nvenc", "container": "mp4"})
        self.assertEqual(valid_entry["routing"], {"profile": "transcode", "routeThresholdMode": "bitrate"})
        self.assertEqual(valid_entry["audio"], {"maxChannels": 6})

    def test_local_api_file_override_route_preview_is_read_only_and_validates_proposals(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "TV" / "Show" / "Show S01E01.mkv"
            missing_row_source = root / "TV" / "Show" / "Show S01E02.mkv"
            outside = root / "Other" / "Outside.mkv"
            for path in (source, missing_row_source, outside):
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(b"media")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.file_overrides_path = resolved.state_root / "file_overrides.json"
            resolved.queue_snapshot_path = resolved.state_root / "Progress" / "queue_snapshot.json"
            resolved.config_data = {
                "SourceMovies": str(resolved.source_movies),
                "SourceTV": str(resolved.source_tv),
                "RoutingProfile": "plex_direct_stream",
                "RouteThresholdMode": "compatibility_advisory",
                "SizeGuardMode": "advisory",
                "VideoCodec": "h264_nvenc",
                "OutputContainer": "mkv",
                "EncodeTuningPreset": "balanced_nvenc",
                "EncodeLadder": "auto",
                "RemuxSafeVideoCodecs": ["h264", "hevc"],
            }
            resolved.file_overrides_path.parent.mkdir(parents=True, exist_ok=True)
            resolved.file_overrides_path.write_text(
                json.dumps(
                    {
                        "version": 1,
                        "entries": {
                            str(source).replace("\\", "/").lower(): {
                                "set_at": "2026-05-31T00:00:00+00:00",
                                "audio": {"maxChannels": 6},
                            }
                        },
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            resolved.queue_snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            resolved.queue_snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": "queue_plan_snapshot.v1",
                        "produced_at": "2026-05-31T12:00:00-04:00",
                        "rows": [
                            {
                                "source_path": str(source),
                                "root_path": str(resolved.source_tv),
                                "media_kind": "tv",
                                "phase": "tv",
                                "relative_path": "Show/Show S01E01.mkv",
                                "display_name": "Show S01E01",
                                "route": "remux",
                                "route_reason": "source is compatible",
                                "route_reason_code": "compatible_source",
                                "queue_index": 1,
                                "queue_total": 1,
                                "global_order": 1,
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            manifest_before = resolved.file_overrides_path.read_text(encoding="utf-8")
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-route-preview-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                missing_status, missing = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {},
                    token=server.token,
                )
                invalid_path_status, invalid_path = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(outside)},
                    token=server.token,
                )
                current_status, current = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(source)},
                    token=server.token,
                )
                remux_status, remux = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(source), "proposed_override": {"routing": {"forceRoute": "remux"}}},
                    token=server.token,
                )
                transcode_status, transcode = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(source), "proposed_override": {"routing": {"forceRoute": "transcode"}}},
                    token=server.token,
                )
                bad_route_status, bad_route = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(source), "proposed_override": {"routing": {"forceRoute": "copy"}}},
                    token=server.token,
                )
                bad_codec_status, bad_codec = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(source), "proposed_override": {"video": {"codec": "vp9"}}},
                    token=server.token,
                )
                bad_container_status, bad_container = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(source), "proposed_override": {"video": {"container": "avi"}}},
                    token=server.token,
                )
                video_only_status, video_only = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(source), "proposed_override": {"video": {"codec": "h264_nvenc"}}},
                    token=server.token,
                )
                burn_status, burn = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {
                        "path": str(source),
                        "proposed_override": {"subtitles": {"burnTrack": {"streamIndex": 3, "language": "eng"}}},
                    },
                    token=server.token,
                )
                burn_remux_status, burn_remux = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {
                        "path": str(source),
                        "proposed_override": {
                            "routing": {"forceRoute": "remux"},
                            "subtitles": {"burnTrack": {"streamIndex": 3}},
                        },
                    },
                    token=server.token,
                )
                missing_row_status, missing_row = self._post_json(
                    f"{server.url}/api/queue/file-overrides/route-preview",
                    {"path": str(missing_row_source)},
                    token=server.token,
                )
            finally:
                server.stop()
            manifest_after = resolved.file_overrides_path.read_text(encoding="utf-8")

        self.assertEqual(missing_status, 200)
        self.assertFalse(missing["ok"])
        self.assertIn("'path' is required", "\n".join(missing.get("errors", [])))
        self.assertEqual(invalid_path_status, 200)
        self.assertFalse(invalid_path["ok"])
        self.assertIn("outside configured source roots", "\n".join(invalid_path.get("errors", [])))
        self.assertEqual(current_status, 200)
        self.assertTrue(current["ok"])
        self.assertEqual(current["schema_version"], "queue_file_override_route_preview.v1")
        self.assertEqual(current["current"]["route"], "remux")
        self.assertEqual(current["current"]["videoCodec"], "copy")
        self.assertEqual(current["proposed"]["route"], "remux")
        self.assertEqual(current["proposed"]["decisionSource"], "current_queue_snapshot")
        self.assertFalse(current["impact"]["will_force_transcode"])
        self.assertEqual(current["impact"]["route_decision_helper"], "queue_snapshot_current_route")
        self.assertEqual(remux_status, 200)
        self.assertTrue(remux["ok"])
        self.assertEqual(remux["proposed"]["route"], "remux")
        self.assertEqual(remux["proposed"]["decisionSource"], "forced_route_preview")
        self.assertFalse(remux["impact"]["will_force_transcode"])
        self.assertEqual(remux["impact"]["estimated_risk"], "low")
        self.assertEqual(transcode_status, 200)
        self.assertTrue(transcode["ok"])
        self.assertEqual(transcode["proposed"]["route"], "transcode")
        self.assertEqual(transcode["proposed"]["videoCodec"], "h264_nvenc")
        self.assertEqual(transcode["proposed"]["decisionSource"], "forced_route_preview")
        self.assertTrue(transcode["impact"]["will_force_transcode"])
        self.assertTrue(transcode["impact"]["will_prevent_remux"])
        self.assertTrue(transcode["impact"]["requires_confirmation"])
        self.assertEqual(bad_route_status, 200)
        self.assertFalse(bad_route["ok"])
        self.assertIn("routing.forceRoute", "\n".join(bad_route.get("errors", [])))
        self.assertEqual(bad_codec_status, 200)
        self.assertFalse(bad_codec["ok"])
        self.assertIn("video.codec", "\n".join(bad_codec.get("errors", [])))
        self.assertEqual(bad_container_status, 200)
        self.assertFalse(bad_container["ok"])
        self.assertIn("video.container", "\n".join(bad_container.get("errors", [])))
        self.assertEqual(video_only_status, 200)
        self.assertTrue(video_only["ok"])
        self.assertEqual(video_only["proposed"]["route"], "transcode")
        self.assertEqual(video_only["proposed"]["source"], "proposed_file_override")
        self.assertEqual(video_only["proposed"]["decisionSource"], "proposed_file_override")
        self.assertTrue(video_only["impact"]["will_force_transcode"])
        self.assertEqual(burn_status, 200)
        self.assertTrue(burn["ok"])
        self.assertEqual(burn["proposed"]["route"], "transcode")
        self.assertTrue(burn["impact"]["will_force_transcode"])
        self.assertTrue(burn["impact"]["will_prevent_remux"])
        burn_warnings = "\n".join(item["message"] for item in burn.get("warnings", []))
        self.assertIn("Subtitle burn-in forces ENCODE", burn_warnings)
        self.assertIn("All selectable output subtitle streams will be dropped", burn_warnings)
        self.assertIn("subtitle-burn encode profile", burn_warnings)
        self.assertEqual(burn_remux_status, 200)
        self.assertFalse(burn_remux["ok"])
        self.assertIn("subtitles.burnTrack", "\n".join(burn_remux.get("errors", [])))
        self.assertEqual(missing_row_status, 200)
        self.assertFalse(missing_row["ok"])
        self.assertIn("queue snapshot row", "\n".join(missing_row.get("errors", [])).lower())
        self.assertEqual(manifest_after, manifest_before)

    def test_local_api_file_override_route_video_persistence_validation_and_effective_metadata(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            source = root / "TV" / "Show" / "Show S01E01.mkv"
            source.parent.mkdir(parents=True, exist_ok=True)
            source.write_bytes(b"media")
            resolved = _resolved(root)
            resolved.state_root = root / "State"
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.file_overrides_path = resolved.state_root / "file_overrides.json"
            resolved.config_data = {
                "SourceMovies": str(resolved.source_movies),
                "SourceTV": str(resolved.source_tv),
                "RoutingProfile": "plex_direct_stream",
                "RouteThresholdMode": "compatibility_advisory",
                "VideoCodec": "hevc_nvenc",
                "OutputContainer": "mkv",
                "EncodeTuningPreset": "balanced_nvenc",
                "EncodeLadder": "auto",
                "CompatibleAudioCodecs": ["aac"],
                "SubKeepLanguages": ["eng"],
                "RemuxSafeVideoCodecs": ["h264", "hevc"],
            }
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(
                facade,
                token="queue-route-video-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                valid_status, valid = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "routing": {
                            "profile": "transcode",
                            "routeThresholdMode": "bitrate",
                        },
                        "video": {
                            "codec": "h264_nvenc",
                            "container": "mp4",
                            "encodePreset": "balanced_nvenc",
                            "encodeLadder": "plex_compat",
                        },
                    },
                    token=server.token,
                )
                read_status, read_payload = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
                effective_status, effective = self._get_json(
                    f"{server.url}/api/queue/file-overrides/effective?path={quote(str(source))}",
                    token=server.token,
                )
                raw_manifest = json.loads(resolved.file_overrides_path.read_text(encoding="utf-8"))
                bad_profile_status, bad_profile = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "routing": {"profile": "transcode;Remove-Item"}},
                    token=server.token,
                )
                bad_codec_status, bad_codec = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "video": {"codec": "vp9"}},
                    token=server.token,
                )
                bad_container_status, bad_container = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "video": {"container": "avi"}},
                    token=server.token,
                )
                unknown_nested_status, unknown_nested = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "routing": {"forceRoute": "transcode"}},
                    token=server.token,
                )
                bad_combo_status, bad_combo = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "routing": {"profile": "remux"},
                        "video": {"codec": "h264_nvenc"},
                    },
                    token=server.token,
                )
                clear_one_status, clear_one = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "clear_fields": ["video.codec"]},
                    token=server.token,
                )
                read_after_clear_status, read_after_clear = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
                unsupported_clear_status, unsupported_clear = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "clear_fields": ["video.rawArgs"]},
                    token=server.token,
                )
                clear_remaining_status, clear_remaining = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "clear_fields": [
                            "routing.profile",
                            "routing.routeThresholdMode",
                            "video.container",
                            "video.encodePreset",
                            "video.encodeLadder",
                        ],
                    },
                    token=server.token,
                )
                read_empty_status, read_empty = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
                audio_status, audio = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {
                        "path": str(source),
                        "audio": {"maxChannels": 6},
                        "subtitles": {"stripAll": False},
                    },
                    token=server.token,
                )
                full_clear_status, full_clear = self._post_json(
                    f"{server.url}/api/queue/file-overrides",
                    {"path": str(source), "clear": True},
                    token=server.token,
                )
                read_full_clear_status, read_full_clear = self._get_json(
                    f"{server.url}/api/queue/file-overrides?path={quote(str(source))}",
                    token=server.token,
                )
            finally:
                server.stop()

        self.assertEqual(valid_status, 200)
        self.assertTrue(valid["ok"])
        self.assertTrue(any("routing.profile" in warning for warning in valid.get("warnings", [])))
        self.assertTrue(any("video.container" in warning for warning in valid.get("warnings", [])))
        self.assertEqual(read_status, 200)
        self.assertTrue(read_payload["has_override"])
        entry = read_payload["entry"]
        self.assertEqual(entry["routing"], {"profile": "transcode", "routeThresholdMode": "bitrate"})
        self.assertEqual(
            entry["video"],
            {
                "codec": "h264_nvenc",
                "container": "mp4",
                "encodePreset": "balanced_nvenc",
                "encodeLadder": "plex_compat",
            },
        )
        manifest_entry = next(iter(raw_manifest["entries"].values()))
        self.assertEqual(sorted(manifest_entry.keys()), ["routing", "set_at", "video"])
        self.assertEqual(effective_status, 200)
        self.assertTrue(effective["ok"])
        route_fields = effective["route_video_effective_fields"]
        self.assertEqual(route_fields["routeProfile"]["source"], "file_override")
        self.assertEqual(route_fields["routeProfile"]["value"], "transcode")
        self.assertTrue(route_fields["routeProfile"]["can_clear_file_field"])
        self.assertTrue(route_fields["routeProfile"]["warnings"])
        self.assertIn({"value": "transcode", "label": "Transcode"}, route_fields["routeProfile"]["choices"])
        self.assertIn({"value": "bitrate", "label": "Bitrate"}, route_fields["routingRouteThresholdMode"]["choices"])
        self.assertEqual(route_fields["videoCodec"]["source"], "file_override")
        self.assertEqual(route_fields["videoCodec"]["inherited"]["value"], "hevc_nvenc")
        self.assertIn({"value": "h264_nvenc", "label": "H264 Nvenc"}, route_fields["videoCodec"]["choices"])
        self.assertIn({"value": "mp4", "label": "Mp4"}, route_fields["videoContainer"]["choices"])
        self.assertIn({"value": "balanced_nvenc", "label": "Balanced Nvenc"}, route_fields["videoEncodePreset"]["choices"])
        self.assertIn({"value": "plex_compat", "label": "Plex Compat"}, route_fields["videoEncodeLadder"]["choices"])
        self.assertEqual(effective["sources"]["video.container"], "file_override")
        self.assertEqual(effective["route_video_processing"]["route"], "transcode")
        self.assertTrue(effective["route_video_processing"]["will_force_transcode"])
        self.assertEqual(effective["route_video_processing"]["container"], "mp4")
        for status, payload, expected in [
            (bad_profile_status, bad_profile, "routing.profile"),
            (bad_codec_status, bad_codec, "video.codec"),
            (bad_container_status, bad_container, "video.container"),
            (unknown_nested_status, unknown_nested, "Unsupported routing field(s): forceRoute"),
            (bad_combo_status, bad_combo, "cannot be combined"),
        ]:
            with self.subTest(expected=expected):
                self.assertEqual(status, 200)
                self.assertFalse(payload["ok"])
                self.assertIn(expected, "\n".join(payload.get("errors", [])))
        self.assertEqual(clear_one_status, 200)
        self.assertTrue(clear_one["ok"])
        self.assertEqual(read_after_clear_status, 200)
        self.assertNotIn("codec", read_after_clear["entry"]["video"])
        self.assertEqual(read_after_clear["entry"]["video"]["container"], "mp4")
        self.assertEqual(read_after_clear["entry"]["routing"]["profile"], "transcode")
        self.assertEqual(unsupported_clear_status, 200)
        self.assertFalse(unsupported_clear["ok"])
        self.assertIn("Unsupported clear_fields path(s): video.rawArgs", "\n".join(unsupported_clear.get("errors", [])))
        self.assertEqual(clear_remaining_status, 200)
        self.assertTrue(clear_remaining["ok"])
        self.assertEqual(read_empty_status, 200)
        self.assertFalse(read_empty["has_override"])
        self.assertEqual(audio_status, 200)
        self.assertTrue(audio["ok"])
        self.assertEqual(full_clear_status, 200)
        self.assertTrue(full_clear["ok"])
        self.assertEqual(read_full_clear_status, 200)
        self.assertFalse(read_full_clear["has_override"])

    def test_local_api_queue_and_rename_preview_contracts(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            media = root / "TV" / "Season 02" / "Serial Experiments Lain E01 Weird 1080p BluRay FLAC 2.0 x264-Chotab.mkv"
            media.parent.mkdir(parents=True, exist_ok=True)
            (root / "Movies").mkdir(parents=True, exist_ok=True)
            media.write_bytes(b"media")
            snapshot_path = root / "State" / "Progress" / "queue_snapshot.json"
            snapshot_path.parent.mkdir(parents=True, exist_ok=True)
            snapshot_path.write_text(
                json.dumps(
                    {
                        "schema_version": "queue_plan_snapshot.v1",
                        "produced_at": "2026-05-07T21:00:00-04:00",
                        "config_path": str(root / "config.psd1"),
                        "local_base": str(root),
                        "source_movies": str(root / "Movies"),
                        "source_tv": str(root / "TV"),
                        "outsource": str(root / "Outsource"),
                        "movie_count_total": 0,
                        "tv_count_total": 1,
                        "priority_count": 0,
                        "runnable_count": 1,
                        "rows": [
                            {
                                "global_order": 1,
                                "phase": "tv",
                                "media_kind": "tv",
                                "queue_index": 1,
                                "queue_total": 1,
                                "is_priority": False,
                                "source_path": str(media),
                                "root_path": str(root / "TV"),
                                "relative_path": "Season 02\\Serial Experiments Lain E01 Weird.mkv",
                                "display_name": media.name,
                                "size_gb": 1.25,
                                "route": "encode",
                                "route_reason_code": "subtitle_srt_required",
                                "route_reason": "needs preferred-language SRT",
                                "blocked_reason": "",
                            }
                        ],
                    }
                ),
                encoding="utf-8",
            )
            resolved = _resolved(root)
            resolved.source_movies = root / "Movies"
            resolved.source_tv = root / "TV"
            resolved.config_data = {
                "RoutingProfile": "plex_direct_stream",
                "SizeGuardMode": "advisory",
                "NetworkRole": "standalone",
                "ApiToken": "secret-token",
                "SourceMovies": str(root / "Movies"),
                "SourceTV": str(root / "TV"),
                "Outsource": str(root / "Outsource"),
                "MinFreeSpaceGB": 0,
                "OutsourceMinFreeSpaceGB": 0,
            }
            resolved.queue_snapshot_path = snapshot_path
            pending_root = root / "PendingServerPush"
            pending_root.mkdir()
            (pending_root / "Movie.mkv").write_bytes(b"abc")
            resolved.pending_push_path = pending_root
            completed_output = root / "Outsource" / "Movie.mkv"
            completed_output.parent.mkdir(parents=True, exist_ok=True)
            completed_output.write_bytes(b"media")
            completed_manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
            completed_manifest.parent.mkdir(parents=True, exist_ok=True)
            completed_manifest.write_text(
                json.dumps(
                    {
                        "source_path": str(media),
                        "output_path": str(completed_output),
                        "route": "remux",
                        "encoded_at": "2026-05-07T21:30:00-04:00",
                        "elapsed_seconds": 30,
                        "output_size": completed_output.stat().st_size,
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            resolved.completed_manifest_path = completed_manifest
            (root / "failures.json").write_text(
                json.dumps(
                    [
                        {
                            "SourcePath": str(media),
                            "JobId": "job-local-encode",
                            "Stage": "encode",
                            "Reason": "No NVENC capable devices found",
                            "Classification": "operator_required",
                            "ErrorCode": "ENCODE_NVENC_FAILED",
                            "RecordedAt": "2026-05-07T22:00:00-04:00",
                            "RetryCount": 3,
                            "RetryLimit": 3,
                        }
                    ]
                ),
                encoding="utf-8",
            )
            failure_markers = root / "State" / "Failed" / "Markers"
            failure_markers.mkdir(parents=True)
            (failure_markers / "marker-1.json").write_text(
                json.dumps(
                    {
                        "source_full_path": str(media),
                        "job_id": "job-local-publish",
                        "stage": "publish",
                        "reason": "Network destination unavailable",
                        "classification": "transient",
                        "error_code": "PUBLISH_UNAVAILABLE",
                        "recorded_at": "2026-05-07T22:30:00-04:00",
                        "retry_count": 1,
                        "retry_limit": 5,
                    }
                ),
                encoding="utf-8",
            )
            resolved.failed_markers_path = failure_markers
            audit_csv = root / "audit_summary_latest.csv"
            audit_priority_csv = root / "audit_priority_latest.csv"
            with audit_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "Path",
                        "RelativePath",
                        "LookupTitle",
                        "MediaType",
                        "EffectiveBucket",
                        "PriorityFixLevel",
                        "PriorityScore",
                        "PrimaryIssueCode",
                        "PrimarySuggestedAction",
                        "IssueMessages",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "Path": str(media),
                        "RelativePath": "Season 02\\Serial Experiments Lain E01 Weird.mkv",
                        "LookupTitle": "Serial Experiments Lain",
                        "MediaType": "TV",
                        "EffectiveBucket": "RERUN_PIPELINE",
                        "PriorityFixLevel": "HIGH",
                        "PriorityScore": "75",
                        "PrimaryIssueCode": "subtitle_srt_required",
                        "PrimarySuggestedAction": "Rerun pipeline.",
                        "IssueMessages": "Preferred-language SRT missing.",
                    }
                )
            with audit_priority_csv.open("w", encoding="utf-8", newline="") as handle:
                writer = csv.DictWriter(
                    handle,
                    fieldnames=[
                        "Path",
                        "RelativePath",
                        "LookupTitle",
                        "MediaType",
                        "EffectiveBucket",
                        "PriorityFixLevel",
                        "PriorityScore",
                        "PrimaryIssueCode",
                        "PrimarySuggestedAction",
                        "IssueMessages",
                    ],
                )
                writer.writeheader()
                writer.writerow(
                    {
                        "Path": str(media),
                        "RelativePath": "Season 02\\Serial Experiments Lain E01 Weird.mkv",
                        "LookupTitle": "Serial Experiments Lain",
                        "MediaType": "TV",
                        "EffectiveBucket": "REVIEW",
                        "PriorityFixLevel": "HIGH",
                        "PriorityScore": "99",
                        "PrimaryIssueCode": "priority_only_issue",
                        "PrimarySuggestedAction": "Use latest priority report.",
                        "IssueMessages": "Priority report row.",
                    }
                )
            (root / "RunLogs").mkdir()
            service = DummyWorkflowFacadeService(root)
            service.cleanup_stale_launch_guards = lambda _resolved_arg: []  # type: ignore[method-assign]
            service.find_related_pipeline_processes = lambda _resolved_arg, **_kwargs: []  # type: ignore[method-assign]
            service.active_job_close_block_messages = lambda _resolved_arg, job_kinds=None: []  # type: ignore[method-assign]
            service.read_progress = lambda _resolved_arg: {}  # type: ignore[method-assign]
            service.read_audit_progress = lambda _resolved_arg: {}  # type: ignore[method-assign]
            service.backfill_completed_manifest = lambda resolved, **_kwargs: (  # type: ignore[method-assign]
                True,
                "\n".join(
                    [
                        "Backfill dry run complete.",
                        "  Sidecars ingested : 4",
                        "  Skipped (bad JSON): 0",
                        f"  Manifest          : {resolved.completed_manifest_path}",
                    ]
                ),
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            facade._autonomy_health_for_resolved = lambda _resolved_arg: {"overall_status": "ready"}  # type: ignore[method-assign]
            reload_calls = {"count": 0}

            def reload_resolved() -> ResolvedPaths:
                reload_calls["count"] += 1
                resolved.config_data["Reloaded"] = True
                return resolved

            server = LocalApiServer(
                facade,
                token="workflow-token",
                resolved_provider=lambda: resolved,
                resolved_reload=reload_resolved,
                audit_root_provider=lambda: str(root),
            )
            server._rename_path_picker = lambda **_kwargs: {  # type: ignore[attr-defined]
                "ok": True,
                "canceled": False,
                "selection_mode": "files",
                "paths": [str(media)],
                "message": "Selected 1 file.",
                "errors": [],
            }
            server._settings_path_picker = lambda **_kwargs: {  # type: ignore[attr-defined]
                "ok": True,
                "canceled": False,
                "selection_mode": "folder",
                "paths": [str(root / "TV")],
                "message": "Selected 1 folder.",
                "errors": [],
            }
            server._pipeline_file_picker = lambda **_kwargs: {  # type: ignore[attr-defined]
                "ok": True,
                "canceled": False,
                "selection_mode": "files",
                "paths": [str(media)],
                "message": "Selected 1 file.",
                "errors": [],
            }
            try:
                server.start()
                queue_status, queue_payload = self._get_json(f"{server.url}/api/queue", token="workflow-token")
                completed_status, completed_payload = self._get_json(f"{server.url}/api/completed", token="workflow-token")
                completed_open_status, completed_open_payload = self._post_json(
                    f"{server.url}/api/completed/open",
                    {"row_key": completed_payload["rows"][0]["row_key"], "target": "output_folder"},
                    token="workflow-token",
                )
                failures_status, failures_payload = self._get_json(f"{server.url}/api/failures", token="workflow-token")
                failure_markers_status, failure_markers_payload = self._get_json(
                    f"{server.url}/api/failures?source=markers",
                    token="workflow-token",
                )
                audit_results_status, audit_results_payload = self._get_json(
                    f"{server.url}/api/audit-results",
                    token="workflow-token",
                )
                priority_audit_status, priority_audit_payload = self._get_json(
                    f"{server.url}/api/audit-results?priority_only=true",
                    token="workflow-token",
                )
                pending_status, pending_payload = self._get_json(
                    f"{server.url}/api/pending-publish",
                    token="workflow-token",
                )
                pending_recovery_plan_status, pending_recovery_plan_payload = self._post_json(
                    f"{server.url}/api/pending-publish/recovery-plan",
                    {"scope": "all"},
                    token="workflow-token",
                )
                close_readiness_status, close_readiness_payload = self._get_json(
                    f"{server.url}/api/backend/close-readiness",
                    token="workflow-token",
                )
                maintenance_status, maintenance_payload = self._get_json(
                    f"{server.url}/api/maintenance",
                    token="workflow-token",
                )
                maintenance_progress_status, maintenance_progress_payload = self._get_json(
                    f"{server.url}/api/maintenance/progress",
                    token="workflow-token",
                )
                release_dry_run_status, release_dry_run_payload = self._post_json(
                    f"{server.url}/api/maintenance/release-dry-run",
                    {"destination_root": str(root / "Deploy"), "include_optional_tools": True},
                    token="workflow-token",
                )
                backfill_dry_run_status, backfill_dry_run_payload = self._post_json(
                    f"{server.url}/api/maintenance/completed-backfill-dry-run",
                    {},
                    token="workflow-token",
                )
                dependency_atlas_status, dependency_atlas_payload = self._post_json(
                    f"{server.url}/api/maintenance/dependency-atlas",
                    {"timeout_seconds": 99999, "min_overview_edge_count": 5},
                    token="workflow-token",
                )
                (root / "docs/generated/dependency-atlas").mkdir(parents=True, exist_ok=True)
                dependency_atlas_open_status, dependency_atlas_open_payload = self._post_json(
                    f"{server.url}/api/maintenance/dependency-atlas/open-folder",
                    {},
                    token="workflow-token",
                )
                schedule_status, schedule_payload = self._get_json(f"{server.url}/api/schedule", token="workflow-token")
                schedule_preview_status, schedule_preview_payload = self._post_json(
                    f"{server.url}/api/schedule/preview",
                    {"enabled": True, "day_windows": {"Monday": "9:00 AM - 10:00 AM"}},
                    token="workflow-token",
                )
                schedule_save_status, schedule_save_payload = self._post_json(
                    f"{server.url}/api/schedule/save",
                    {
                        "enabled": True,
                        "day_windows": {"Monday": "9:00 AM - 10:00 AM"},
                        "confirm_save": True,
                    },
                    token="workflow-token",
                )
                denied_status, denied = self._post_json(
                    f"{server.url}/api/rename/preview",
                    {"paths": [str(media)], "mode": "tv", "season": "S02"},
                )
                rename_status, rename_payload = self._post_json(
                    f"{server.url}/api/rename/preview",
                    {"paths": [str(media)], "mode": "tv", "season": "S02", "use_pipeline_naming_preview": False},
                    token="workflow-token",
                )
                rename_browse_status, rename_browse_payload = self._post_json(
                    f"{server.url}/api/rename/browse",
                    {"selection_mode": "files", "initial_path": str(media.parent)},
                    token="workflow-token",
                )
                pipeline_browse_status, pipeline_browse_payload = self._post_json(
                    f"{server.url}/api/pipeline/browse-file",
                    {"selection_mode": "files", "initial_path": str(media.parent)},
                    token="workflow-token",
                )
                settings_browse_status, settings_browse_payload = self._post_json(
                    f"{server.url}/api/settings/browse-path",
                    {"setting_key": "SourceTV", "selection_mode": "folder", "initial_path": str(root)},
                    token="workflow-token",
                )
                rename_apply_status, rename_apply_payload = self._post_json(
                    f"{server.url}/api/rename/apply",
                    {
                        "paths": [str(media)],
                        "mode": "tv",
                        "season": "S02",
                        "use_pipeline_naming_preview": False,
                        "selected_sources": [str(media)],
                        "confirm_apply": True,
                    },
                    token="workflow-token",
                )
                validate_status, validate_payload = self._post_json(
                    f"{server.url}/api/settings/validate",
                    {"values": {"LocalBase": str(root / "Scratch"), "SourceTV": str(root / "TV")}},
                    token="workflow-token",
                )
                settings_patch_status, settings_patch_payload = self._post_json(
                    f"{server.url}/api/settings/preview-patch",
                    {"changes": {"RoutingProfile": "plex_direct_play"}},
                    token="workflow-token",
                )
                settings_save_patch_status, settings_save_patch_payload = self._post_json(
                    f"{server.url}/api/settings/save-patch",
                    {"changes": {"RoutingProfile": "plex_direct_play"}, "confirm_save": True},
                    token="workflow-token",
                )
                settings_reload_status, settings_reload_payload = self._post_json(
                    f"{server.url}/api/settings/reload",
                    {},
                    token="workflow-token",
                )
                diagnostics_open_status, diagnostics_open_payload = self._post_json(
                    f"{server.url}/api/diagnostics/open",
                    {"target": "run_logs"},
                    token="workflow-token",
                )
                control_status, control_payload = self._post_json(
                    f"{server.url}/api/pipeline/control",
                    {"action": "stop"},
                    token="workflow-token",
                )
                stop_flag_exists = resolved.stop_flag.exists()
                start_status, start_payload = self._post_json(
                    f"{server.url}/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 3},
                    token="workflow-token",
                )
                audit_status, audit_payload = self._post_json(
                    f"{server.url}/api/audit/start",
                    {"library_root": str(root / "Outsource"), "include_sidecars": True},
                    token="workflow-token",
                )
                rerun_csv = root / "rerun.csv"
                rerun_csv.write_text("enabled,source_path\ntrue,C:\\Media\\Movie.mkv\n", encoding="utf-8")
                rerun_status, rerun_payload = self._post_json(
                    f"{server.url}/api/rerun/start",
                    {"csv_path": str(rerun_csv)},
                    token="workflow-token",
                )
                command_history_status, command_history_payload = self._get_json(
                    f"{server.url}/api/commands?limit=20",
                    token="workflow-token",
                )
            finally:
                server.stop()

        self.assertEqual(queue_status, 200)
        self.assertEqual(queue_payload["schema_version"], "desktop_queue_preview.v1")
        self.assertEqual(queue_payload["rows"][0]["route_name"], "encode")
        self.assertEqual(completed_status, 200)
        self.assertEqual(completed_payload["schema_version"], "desktop_completed_preview.v1")
        self.assertEqual(completed_payload["count"], 1)
        self.assertEqual(completed_payload["inventory_progress"]["schema_version"], "desktop_completed_inventory_progress.v1")
        self.assertEqual(completed_payload["progress_bars"][0]["id"], "completed_inventory")
        self.assertEqual(completed_payload["rows"][0]["route_label"], "REMUX")
        self.assertEqual(completed_payload["validation_state"]["schema_version"], "desktop_validation_state.v1")
        self.assertEqual(completed_payload["completed_pending_proof"]["schema_version"], "desktop_completed_pending_proof.v1")
        self.assertEqual(completed_payload["completed_pending_proof"]["evidence_authority"], "backend")
        self.assertIn(completed_payload["validation_state"]["status_state"], {"validation-needed", "blocked"})
        self.assertIn(completed_payload["rows"][0]["validation_status_state"], {"validation-needed", "blocked"})
        self.assertEqual(completed_open_status, 200)
        self.assertEqual(completed_open_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(completed_open_payload["command"], "completed.open")
        self.assertEqual(completed_open_payload["data"]["target"], "output_folder")
        self.assertEqual(failures_status, 200)
        self.assertEqual(failures_payload["schema_version"], "desktop_failure_preview.v1")
        self.assertEqual(failures_payload["count"], 1)
        self.assertEqual(failures_payload["rows"][0]["error_code"], "ENCODE_NVENC_FAILED")
        self.assertEqual(failures_payload["operator_required_count"], 1)
        self.assertEqual(failures_payload["retry_state"]["schema_version"], "desktop_retry_state.v1")
        self.assertEqual(failures_payload["retry_state"]["blocked_count"], 1)
        self.assertEqual(failure_markers_status, 200)
        self.assertEqual(failure_markers_payload["source_kind"], "markers")
        self.assertEqual(failure_markers_payload["rows"][0]["error_code"], "PUBLISH_UNAVAILABLE")
        self.assertEqual(failure_markers_payload["retry_state"]["status_state"], "retrying")
        self.assertEqual(failure_markers_payload["retry_state"]["rows"][0]["retry_route_or_command"], "automatic_next_queue_pass")
        self.assertEqual(audit_results_status, 200)
        self.assertEqual(audit_results_payload["schema_version"], "desktop_audit_preview.v1")
        self.assertEqual(audit_results_payload["count"], 1)
        self.assertEqual(audit_results_payload["rows"][0]["primary_issue_code"], "subtitle_srt_required")
        self.assertEqual(audit_results_payload["high_priority_count"], 1)
        self.assertEqual(priority_audit_status, 200)
        self.assertTrue(priority_audit_payload["priority_only"])
        self.assertEqual(priority_audit_payload["rows"][0]["primary_issue_code"], "priority_only_issue")
        self.assertEqual(pending_status, 200)
        self.assertEqual(pending_payload["schema_version"], "desktop_pending_publish_preview.v1")
        self.assertEqual(pending_payload["retry_budget"]["schema_version"], "desktop_pending_publish_retry_budget.v1")
        self.assertEqual(pending_payload["retry_budget"]["exhausted_count"], 0)
        self.assertEqual(pending_payload["drain_confidence"]["schema_version"], "desktop_pending_drain_confidence.v1")
        self.assertEqual(pending_payload["drain_confidence"]["evidence_authority"], "backend")
        self.assertEqual(pending_payload["inventory_progress"]["schema_version"], "desktop_pending_publish_inventory_progress.v1")
        self.assertEqual(pending_payload["progress_bars"][0]["id"], "pending_inventory")
        self.assertEqual(pending_payload["rows"][0]["state"], "orphan_payload")
        self.assertEqual(pending_recovery_plan_status, 200)
        self.assertEqual(pending_recovery_plan_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(pending_recovery_plan_payload["command"], "pending_publish.recovery_plan_dry_run")
        self.assertTrue(pending_recovery_plan_payload["ok"])
        self.assertEqual(pending_recovery_plan_payload["data"]["schema_version"], "pending_publish_recovery_plan.v1")
        self.assertTrue(pending_recovery_plan_payload["data"]["dry_run_only"])
        self.assertFalse(pending_recovery_plan_payload["data"]["would_mutate"])
        self.assertEqual(close_readiness_status, 200)
        self.assertEqual(close_readiness_payload["schema_version"], "desktop_close_readiness.v1")
        self.assertFalse(close_readiness_payload["safe_to_close"])
        self.assertEqual(close_readiness_payload["state"], "processing")
        self.assertEqual(maintenance_status, 200)
        self.assertEqual(maintenance_payload["schema_version"], "desktop_maintenance_workspace.v1")
        self.assertEqual(maintenance_payload["warning_count"], 1)
        self.assertEqual(maintenance_payload["health_progress"]["schema_version"], "desktop_maintenance_health_progress.v1")
        self.assertEqual(maintenance_progress_status, 200)
        self.assertEqual(maintenance_progress_payload["schema_version"], "desktop_maintenance_health_progress.v1")
        self.assertEqual(maintenance_progress_payload["progress_bars"][0]["id"], "maintenance_health")
        self.assertEqual(release_dry_run_status, 200)
        self.assertEqual(release_dry_run_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(release_dry_run_payload["command"], "maintenance.release_dry_run")
        self.assertTrue(release_dry_run_payload["ok"])
        self.assertFalse(release_dry_run_payload["data"]["manifest_exists"])
        self.assertFalse(release_dry_run_payload["data"]["zip_exists"])
        self.assertEqual(release_dry_run_payload["data"]["release_progress"]["schema_version"], "desktop_release_package_progress.v1")
        self.assertEqual(release_dry_run_payload["data"]["progress_bars"][0]["id"], "release_package")
        self.assertEqual(backfill_dry_run_status, 200)
        self.assertEqual(backfill_dry_run_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(backfill_dry_run_payload["command"], "maintenance.completed_backfill_dry_run")
        self.assertTrue(backfill_dry_run_payload["ok"])
        self.assertEqual(backfill_dry_run_payload["data"]["backfill_progress"]["schema_version"], "desktop_maintenance_backfill_progress.v1")
        self.assertEqual(backfill_dry_run_payload["data"]["progress_bars"][0]["id"], "maintenance_backfill")
        self.assertEqual(backfill_dry_run_payload["data"]["sidecars_ingested"], "4")
        self.assertFalse(backfill_dry_run_payload["data"]["writes_manifest"])
        self.assertEqual(dependency_atlas_status, 200)
        self.assertEqual(dependency_atlas_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(dependency_atlas_payload["command"], "maintenance.dependency_atlas")
        self.assertTrue(dependency_atlas_payload["ok"])
        self.assertFalse(dependency_atlas_payload["data"]["writes_media"])
        self.assertEqual(dependency_atlas_payload["data"]["dependency_atlas_progress"]["schema_version"], "desktop_dependency_atlas_progress.v1")
        self.assertEqual(dependency_atlas_payload["data"]["progress_bars"][0]["id"], "dependency_atlas")
        self.assertEqual(dependency_atlas_open_status, 200)
        self.assertEqual(dependency_atlas_open_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(dependency_atlas_open_payload["command"], "maintenance.dependency_atlas_open_folder")
        self.assertTrue(dependency_atlas_open_payload["ok"])
        self.assertEqual(dependency_atlas_open_payload["data"]["target"], "dependency_atlas_folder")
        self.assertFalse(dependency_atlas_open_payload["data"]["writes_media"])
        self.assertFalse(dependency_atlas_open_payload["data"]["writes_dependency_atlas"])
        self.assertEqual(schedule_status, 200)
        self.assertEqual(schedule_payload["schema_version"], "desktop_schedule_workspace.v1")
        self.assertIn("day_summaries", schedule_payload)
        self.assertEqual(schedule_preview_status, 200)
        self.assertEqual(schedule_preview_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(schedule_preview_payload["command"], "schedule.preview")
        self.assertFalse(schedule_preview_payload["data"]["writes_app_state"])
        self.assertEqual(schedule_save_status, 200)
        self.assertEqual(schedule_save_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(schedule_save_payload["command"], "schedule.save")
        self.assertTrue(schedule_save_payload["ok"])
        self.assertTrue(schedule_save_payload["data"]["writes_app_state"])
        self.assertEqual(denied_status, 401)
        self.assertEqual(denied["error"], "unauthorized")
        self.assertEqual(rename_status, 200)
        self.assertEqual(rename_payload["schema_version"], "desktop_rename_preview.v1")
        self.assertEqual(rename_payload["rows"][0]["pipeline_guess"], "Serial Experiments Lain - S02E01 - Weird.mkv")
        self.assertEqual(rename_payload["confidence_counts"], {"medium": 1})
        self.assertEqual(rename_payload["preview_source_counts"], {"auto_tv_heuristic": 1})
        self.assertEqual(rename_payload["change_kind_counts"], {"rename": 1})
        self.assertEqual(rename_payload["active_template"], "tv_standard")
        self.assertTrue(any(item["key"] == "tv_no_episode_title" for item in rename_payload["template_catalog"]))
        self.assertEqual(rename_browse_status, 200)
        self.assertEqual(rename_browse_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(rename_browse_payload["command"], "rename.browse")
        self.assertTrue(rename_browse_payload["ok"])
        self.assertEqual(rename_browse_payload["data"]["paths"], [str(media)])
        self.assertEqual(rename_browse_payload["data"]["selection_mode"], "files")
        self.assertEqual(pipeline_browse_status, 200)
        self.assertEqual(pipeline_browse_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(pipeline_browse_payload["command"], "pipeline.browse_file")
        self.assertTrue(pipeline_browse_payload["ok"])
        self.assertEqual(pipeline_browse_payload["data"]["schema_version"], "desktop_pipeline_single_file_browse.v1")
        self.assertEqual(pipeline_browse_payload["data"]["selected_path"], str(media))
        self.assertEqual(pipeline_browse_payload["data"]["selection_mode"], "files")
        self.assertFalse(pipeline_browse_payload["data"]["writes_config"])
        self.assertTrue(pipeline_browse_payload["data"]["stages_only"])
        self.assertFalse(pipeline_browse_payload["data"]["launches_work"])
        self.assertEqual(pipeline_browse_payload["data"]["validation"]["status_state"], "ready")
        self.assertEqual(settings_browse_status, 200)
        self.assertEqual(settings_browse_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(settings_browse_payload["command"], "settings.browse_path")
        self.assertTrue(settings_browse_payload["ok"])
        self.assertEqual(settings_browse_payload["data"]["schema_version"], "desktop_settings_path_browse.v1")
        self.assertEqual(settings_browse_payload["data"]["selected_path"], str(root / "TV"))
        self.assertEqual(settings_browse_payload["data"]["setting_key"], "SourceTV")
        self.assertFalse(settings_browse_payload["data"]["writes_config"])
        self.assertTrue(settings_browse_payload["data"]["stages_only"])
        self.assertEqual(settings_browse_payload["data"]["validation"]["status_state"], "ready")
        self.assertEqual(rename_apply_status, 200)
        self.assertEqual(rename_apply_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(rename_apply_payload["command"], "rename.apply")
        self.assertTrue(rename_apply_payload["ok"], rename_apply_payload)
        Path(str(rename_apply_payload["data"]["undo_manifest"])).unlink(missing_ok=True)
        self.assertEqual(validate_status, 200)
        self.assertEqual(validate_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(validate_payload["command"], "settings.validate")
        self.assertEqual(settings_patch_status, 200)
        self.assertEqual(settings_patch_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(settings_patch_payload["command"], "settings.preview_patch")
        self.assertFalse(settings_patch_payload["data"]["writes_config"])
        self.assertEqual(settings_patch_payload["data"]["settings_progress"]["schema_version"], "desktop_settings_save_reload_progress.v1")
        self.assertIn("RoutingProfile", settings_patch_payload["data"]["changed_keys"])
        self.assertEqual(settings_patch_payload["data"]["risk_summary"]["schema_version"], "settings_patch_risk_summary.v1")
        self.assertNotIn("secret-token", "\n".join(settings_patch_payload["data"]["redacted_diff_lines"]))
        self.assertEqual(settings_save_patch_status, 200)
        self.assertEqual(settings_save_patch_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(settings_save_patch_payload["command"], "settings.save_patch")
        self.assertTrue(settings_save_patch_payload["ok"])
        self.assertTrue(settings_save_patch_payload["data"]["writes_config"])
        self.assertTrue(settings_save_patch_payload["data"]["reloaded"])
        self.assertEqual(settings_save_patch_payload["data"]["settings_progress"]["status"], "complete")
        self.assertEqual(settings_save_patch_payload["data"]["progress_bars"][0]["percent"], 100.0)
        self.assertIn("risk_summary", settings_save_patch_payload["data"])
        self.assertEqual(settings_reload_status, 200)
        self.assertEqual(settings_reload_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(settings_reload_payload["command"], "settings.reload")
        self.assertEqual(settings_reload_payload["data"]["key_count"], len(resolved.config_data))
        self.assertEqual(settings_reload_payload["data"]["settings_progress"]["schema_version"], "desktop_settings_reload_progress.v1")
        self.assertEqual(settings_reload_payload["data"]["progress_bars"][0]["percent"], 100.0)
        self.assertEqual(reload_calls["count"], 2)
        self.assertEqual(diagnostics_open_status, 200)
        self.assertEqual(diagnostics_open_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(diagnostics_open_payload["command"], "diagnostics.open")
        self.assertEqual(diagnostics_open_payload["data"]["target"], "run_logs")
        self.assertEqual(
            service.opened_paths,
            [
                completed_output.parent,
                root / "docs/generated/dependency-atlas",
                root / "RunLogs",
            ],
        )
        self.assertEqual(control_status, 200)
        self.assertEqual(control_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(control_payload["command"], "pipeline.control.stop")
        self.assertTrue(stop_flag_exists)
        self.assertEqual(start_status, 200)
        self.assertEqual(start_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(start_payload["command"], "pipeline.start")
        self.assertEqual(start_payload["data"]["mode"], "validate")
        self.assertEqual(audit_status, 200)
        self.assertEqual(audit_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(audit_payload["command"], "audit.start")
        self.assertEqual(audit_payload["data"]["pid"], 24681)
        self.assertEqual(rerun_status, 200)
        self.assertEqual(rerun_payload["schema_version"], "desktop_command_result.v1")
        self.assertEqual(rerun_payload["command"], "rerun.start")
        self.assertEqual(rerun_payload["data"]["pid"], 24682)
        self.assertEqual(command_history_status, 200)
        self.assertEqual(command_history_payload["schema_version"], "desktop_command_history.v1")
        self.assertGreaterEqual(command_history_payload["count"], 10)
        self.assertEqual(command_history_payload["entries"][0]["command"], "rerun.start")
        self.assertTrue(any(entry["command"] == "schedule.save" for entry in command_history_payload["entries"]))
        self.assertTrue(any(entry["command"] == "settings.save_patch" for entry in command_history_payload["entries"]))
        rerun_entry = command_history_payload["entries"][0]
        self.assertEqual(rerun_entry["data"]["pid"], 24682)
        self.assertEqual(rerun_entry["request"]["csv_path"], str(rerun_csv))
        settings_save_entry = next(entry for entry in command_history_payload["entries"] if entry["command"] == "settings.save_patch")
        self.assertTrue(settings_save_entry["data"]["writes_config"])
        self.assertEqual(settings_save_entry["request"]["changes"]["RoutingProfile"], "plex_direct_play")
        self.assertTrue(settings_save_entry["request"]["confirm_save"])

    def test_local_api_rename_apply_rejects_absent_or_false_confirmation_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            media = root / "Serial Experiments Lain E01 Weird.mkv"
            media.write_text("media", encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="rename-token", resolved_provider=lambda: _resolved(root))
            payload = {
                "paths": [str(media)],
                "mode": "tv",
                "show_name": "Serial Experiments Lain",
                "season": "S01",
                "start_episode": "E01",
                "selected_sources": [str(media)],
                "use_pipeline_naming_preview": False,
            }
            try:
                server.start()
                missing_status, missing = self._post_json(
                    f"{server.url}/api/rename/apply",
                    payload,
                    token="rename-token",
                )
                false_status, false = self._post_json(
                    f"{server.url}/api/rename/apply",
                    {**payload, "confirm_apply": False},
                    token="rename-token",
                )
                string_false_status, string_false = self._post_json(
                    f"{server.url}/api/rename/apply",
                    {**payload, "confirm_apply": "false"},
                    token="rename-token",
                )
            finally:
                server.stop()
            destination = root / "Serial Experiments Lain - S01E01 - Weird.mkv"
            media_still_exists = media.exists()
            destination_exists = destination.exists()

        self.assertEqual(missing_status, 200)
        self.assertEqual(false_status, 200)
        self.assertEqual(string_false_status, 400)
        for result in (missing, false):
            self.assertEqual(result["schema_version"], "desktop_command_result.v1")
            self.assertEqual(result["command"], "rename.apply")
            self.assertFalse(result["ok"])
            self.assertEqual(result["severity"], "warning")
            self.assertIn("confirmation", result["message"].lower())
            self.assertIn("confirm_apply must be true.", result["warnings"])
        self.assertIn("invalid API command payload", string_false["error"])
        self.assertIn("confirm_apply", string_false["error"])
        self.assertTrue(media_still_exists)
        self.assertFalse(destination_exists)

    def test_local_api_rename_apply_blocks_active_work_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            media = root / "Serial Experiments Lain E01 Weird.mkv"
            media.write_text("media", encoding="utf-8")
            service = DummyWorkflowFacadeService(root)
            resolved = _resolved(root)
            service.cleanup_stale_launch_guards = lambda _resolved_arg: []  # type: ignore[method-assign]
            service.find_related_pipeline_processes = lambda _resolved_arg, job_kinds=None: []  # type: ignore[method-assign]
            service.active_job_close_block_messages = (  # type: ignore[method-assign]
                lambda _resolved_arg, job_kinds=None: ["ActiveJobs record launch.json reports pipeline work as active."]
            )
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="rename-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                status, result = self._post_json(
                    f"{server.url}/api/rename/apply",
                    {
                        "paths": [str(media)],
                        "mode": "tv",
                        "show_name": "Serial Experiments Lain",
                        "season": "S01",
                        "start_episode": "E01",
                        "selected_sources": [str(media)],
                        "use_pipeline_naming_preview": False,
                        "confirm_apply": True,
                    },
                    token="rename-token",
                )
            finally:
                server.stop()
            destination = root / "Serial Experiments Lain - S01E01 - Weird.mkv"
            media_still_exists = media.exists()
            destination_exists = destination.exists()

        self.assertEqual(status, 200)
        self.assertEqual(result["schema_version"], "desktop_command_result.v1")
        self.assertEqual(result["command"], "rename.apply")
        self.assertFalse(result["ok"])
        self.assertEqual(result["severity"], "error")
        self.assertEqual(result["errors"], ["active_work"])
        self.assertIn("ActiveJobs still reports active work", result["message"])
        self.assertTrue(media_still_exists)
        self.assertFalse(destination_exists)

    def test_local_api_injects_rename_media_roots_and_requires_outside_root_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            configured = root / "ConfiguredMovies"
            outside = root / "StandaloneFolder"
            configured.mkdir()
            outside.mkdir()
            media = outside / "Example Movie 2024 1080p BluRay.mkv"
            media.write_text("media", encoding="utf-8")
            resolved = _resolved(root)
            resolved.local_base = root / "Scratch"
            resolved.state_root = resolved.local_base / "State"
            resolved.source_movies = configured
            resolved.source_tv = root / "ConfiguredTV"
            resolved.config_data = {"Outsource": str(root / "Outsource")}
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="rename-token", resolved_provider=lambda: resolved)
            spoofed_undo_root = root / "SpoofedUndo"
            apply_payload = {
                "paths": [str(media)],
                "mode": "movie",
                "movie_title": "Example Movie",
                "movie_year": "2024",
                "selected_sources": [str(media)],
                "confirm_apply": True,
                "use_pipeline_naming_preview": False,
            }
            spoofed_apply_payload = {
                **apply_payload,
                "_configured_media_roots": [str(outside)],
                "_rename_undo_manifest_root": str(spoofed_undo_root),
            }
            try:
                server.start()
                preview_status, preview = self._post_json(
                    f"{server.url}/api/rename/preview",
                    {
                        "paths": [str(media)],
                        "mode": "movie",
                        "movie_title": "Example Movie",
                        "movie_year": "2024",
                        "_configured_media_roots": [str(outside)],
                        "_rename_undo_manifest_root": str(spoofed_undo_root),
                    },
                    token="rename-token",
                )
                spoofed_apply_status, spoofed_apply = self._post_json(
                    f"{server.url}/api/rename/apply",
                    spoofed_apply_payload,
                    token="rename-token",
                )
                rejected_status, rejected = self._post_json(
                    f"{server.url}/api/rename/apply",
                    apply_payload,
                    token="rename-token",
                )
                string_rejected_status, string_rejected = self._post_json(
                    f"{server.url}/api/rename/apply",
                    {**apply_payload, "allow_outside_configured_roots": "false"},
                    token="rename-token",
                )
                allowed_status, allowed = self._post_json(
                    f"{server.url}/api/rename/apply",
                    {**apply_payload, "allow_outside_configured_roots": True},
                    token="rename-token",
                )
            finally:
                server.stop()
            destination = outside / "Example Movie (2024).mkv"
            destination_exists = destination.exists()
            media_exists = media.exists()
            undo_manifest = Path(str(allowed["data"]["undo_manifest"]))
            undo_parent = undo_manifest.parent
            undo_manifest_exists = undo_manifest.exists()
            undo_manifest.unlink(missing_ok=True)

        self.assertEqual(preview_status, 200)
        self.assertEqual(preview["rows"][0]["path_authority"], "outside_configured_roots")
        self.assertEqual(spoofed_apply_status, 400)
        self.assertIn("_configured_media_roots", spoofed_apply["error"])
        self.assertEqual(rejected_status, 200)
        self.assertFalse(rejected["ok"])
        self.assertIn("outside configured media roots", rejected["message"])
        self.assertEqual(string_rejected_status, 400)
        self.assertIn("allow_outside_configured_roots", string_rejected["error"])
        self.assertEqual(allowed_status, 200)
        self.assertTrue(allowed["ok"])
        self.assertTrue(destination_exists)
        self.assertFalse(media_exists)
        self.assertTrue(undo_manifest_exists)
        self.assertEqual(undo_parent, root / "Scratch" / "State" / "RenameUndo")
        self.assertFalse(spoofed_undo_root.exists())

    def test_local_api_serves_read_only_web_prototype(self) -> None:
        from urllib.request import urlopen

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            service = DummyFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v6-test")
            server = LocalApiServer(facade, token="web-token", resolved_provider=lambda: _resolved(root))
            try:
                server.start()
                with urlopen(f"{server.url}/", timeout=5) as response:  # noqa: S310 - localhost test server
                    html = response.read().decode("utf-8")
                    content_type = response.headers.get("Content-Type", "")
                    set_cookie = response.headers.get("Set-Cookie", "")
                with urlopen(f"{server.url}/assets/app/lifecycle.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    app_lifecycle_js = response.read().decode("utf-8")
                    app_lifecycle_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/app/topbar.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    app_topbar_js = response.read().decode("utf-8")
                    app_topbar_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/app/closeReadiness.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    app_close_readiness_js = response.read().decode("utf-8")
                    app_close_readiness_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/app/tauriLifecycle.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    app_tauri_lifecycle_js = response.read().decode("utf-8")
                    app_tauri_lifecycle_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/app/refresh.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    app_refresh_js = response.read().decode("utf-8")
                    app_refresh_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/app/home.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    app_home_js = response.read().decode("utf-8")
                    app_home_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/app/homeReadiness.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    app_home_readiness_js = response.read().decode("utf-8")
                    app_home_readiness_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/app/rowOpenActions.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    app_row_open_actions_js = response.read().decode("utf-8")
                    app_row_open_actions_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/app/layoutManager.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    app_layout_manager_js = response.read().decode("utf-8")
                    app_layout_manager_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/app.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    app_parent_js = response.read().decode("utf-8")
                    js_content_type = response.headers.get("Content-Type", "")
                js = "\n".join((
                    app_lifecycle_js,
                    app_topbar_js,
                    app_close_readiness_js,
                    app_tauri_lifecycle_js,
                    app_refresh_js,
                    app_home_js,
                    app_home_readiness_js,
                    app_row_open_actions_js,
                    app_layout_manager_js,
                    app_parent_js,
                ))
                with urlopen(f"{server.url}/assets/apiClient.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    api_client_js = response.read().decode("utf-8")
                    api_client_content_type = response.headers.get("Content-Type", "")
                dom_helper_asset_paths = [
                    "assets/dom/query.js",
                    "assets/dom/text.js",
                    "assets/dom/status.js",
                    "assets/dom/filtering.js",
                    "assets/dom/table.js",
                ]
                dom_helper_parts = []
                dom_helper_child_content_types = {}
                for asset_path in dom_helper_asset_paths:
                    with urlopen(f"{server.url}/{asset_path}", timeout=5) as response:  # noqa: S310 - localhost test server
                        dom_helper_parts.append(response.read().decode("utf-8"))
                        dom_helper_child_content_types[asset_path] = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/domHelpers.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    dom_helper_parts.append(response.read().decode("utf-8"))
                    dom_helpers_content_type = response.headers.get("Content-Type", "")
                dom_helpers_js = "\n".join(dom_helper_parts)
                with urlopen(f"{server.url}/assets/formatters.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    formatters_js = response.read().decode("utf-8")
                    formatters_content_type = response.headers.get("Content-Type", "")
                command_history_parts = []
                command_history_content_type = ""
                for asset_path in COMMAND_HISTORY_ASSET_ORDER:
                    with urlopen(f"{server.url}{asset_path}", timeout=5) as response:  # noqa: S310 - localhost test server
                        command_history_parts.append(response.read().decode("utf-8"))
                        if asset_path == "/assets/commandHistory.js":
                            command_history_content_type = response.headers.get("Content-Type", "")
                command_history_js = "\n".join(command_history_parts)
                with urlopen(f"{server.url}/assets/diagnosticsBridge.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    diagnostics_bridge_js = response.read().decode("utf-8")
                    diagnostics_bridge_content_type = response.headers.get("Content-Type", "")
                completed_view_evidence_parts = []
                completed_view_evidence_child_content_types = {}
                for asset_path in (
                    "/assets/completed/evidence/commands.js",
                    "/assets/completed/evidence/filterScope.js",
                    "/assets/completed/evidence/acceptance.js",
                    "/assets/completed/evidence/routeAgreement.js",
                ):
                    with urlopen(f"{server.url}{asset_path}", timeout=5) as response:  # noqa: S310 - localhost test server
                        completed_view_evidence_parts.append(response.read().decode("utf-8"))
                        completed_view_evidence_child_content_types[asset_path] = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/completedView.evidence.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    completed_view_evidence_parts.append(response.read().decode("utf-8"))
                    completed_view_evidence_content_type = response.headers.get("Content-Type", "")
                completed_view_evidence_js = "\n".join(completed_view_evidence_parts)
                with urlopen(f"{server.url}/assets/completedView.proof.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    completed_view_proof_js = response.read().decode("utf-8")
                    completed_view_proof_content_type = response.headers.get("Content-Type", "")
                completed_view_review_asset_paths = [
                    "assets/completed/review/integrity.js",
                    "assets/completed/review/sizeReview.js",
                    "assets/completed/review/healthSignals.js",
                    "assets/completed/review/reviewRows.js",
                    "assets/completed/review/investigationFilters.js",
                ]
                completed_view_review_parts = []
                completed_view_review_child_content_types = {}
                for asset_path in completed_view_review_asset_paths:
                    with urlopen(f"{server.url}/{asset_path}", timeout=5) as response:  # noqa: S310 - localhost test server
                        completed_view_review_parts.append(response.read().decode("utf-8"))
                        completed_view_review_child_content_types[asset_path] = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/completedView.review.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    completed_view_review_parts.append(response.read().decode("utf-8"))
                    completed_view_review_content_type = response.headers.get("Content-Type", "")
                completed_view_review_js = "\n".join(completed_view_review_parts)
                with urlopen(f"{server.url}/assets/completedView.diagnostics.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    completed_view_diagnostics_js = response.read().decode("utf-8")
                    completed_view_diagnostics_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/completed/statusBoards.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    completed_view_status_boards_js = response.read().decode("utf-8")
                    completed_view_status_boards_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/completed/openActions.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    completed_view_open_actions_js = response.read().decode("utf-8")
                    completed_view_open_actions_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/completed/selection.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    completed_view_selection_js = response.read().decode("utf-8")
                    completed_view_selection_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/completed/filters.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    completed_view_filters_js = response.read().decode("utf-8")
                    completed_view_filters_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/completed/table.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    completed_view_table_js = response.read().decode("utf-8")
                    completed_view_table_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/completedView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    completed_view_js = response.read().decode("utf-8")
                    completed_view_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/queueView.summary.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    queue_view_summary_js = response.read().decode("utf-8")
                    queue_view_summary_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/queueView.review.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    queue_view_review_js = response.read().decode("utf-8")
                    queue_view_review_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/queueView.detail.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    queue_view_detail_js = response.read().decode("utf-8")
                    queue_view_detail_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/queueView.launch.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    queue_view_launch_js = response.read().decode("utf-8")
                    queue_view_launch_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/queue/selection.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    queue_view_selection_js = response.read().decode("utf-8")
                    queue_view_selection_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/queue/openActions.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    queue_view_open_actions_js = response.read().decode("utf-8")
                    queue_view_open_actions_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/queue/table.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    queue_view_table_js = response.read().decode("utf-8")
                    queue_view_table_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/queueView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    queue_view_js = response.read().decode("utf-8")
                    queue_view_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/pendingPublish/summary.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    pending_publish_summary_js = response.read().decode("utf-8")
                    pending_publish_summary_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/pendingPublish/details.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    pending_publish_details_js = response.read().decode("utf-8")
                    pending_publish_details_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/pendingPublish/filters.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    pending_publish_filters_js = response.read().decode("utf-8")
                    pending_publish_filters_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/pendingPublishView.recovery.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    pending_publish_recovery_js = response.read().decode("utf-8")
                    pending_publish_recovery_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/pendingPublishView.diagnostics.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    pending_publish_diagnostics_js = response.read().decode("utf-8")
                    pending_publish_diagnostics_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/pendingPublishView.drain.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    pending_publish_drain_js = response.read().decode("utf-8")
                    pending_publish_drain_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/pendingPublishView.confidence.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    pending_publish_confidence_js = response.read().decode("utf-8")
                    pending_publish_confidence_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/pendingPublishView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    pending_publish_view_js = response.read().decode("utf-8")
                    pending_publish_view_content_type = response.headers.get("Content-Type", "")
                pending_publish_view_js = "\n".join([
                    pending_publish_summary_js,
                    pending_publish_details_js,
                    pending_publish_filters_js,
                    pending_publish_recovery_js,
                    pending_publish_diagnostics_js,
                    pending_publish_drain_js,
                    pending_publish_confidence_js,
                    pending_publish_view_js,
                ])
                with urlopen(f"{server.url}/assets/crossPageContextView.conflict.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    cross_page_conflict_js = response.read().decode("utf-8")
                    cross_page_conflict_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/crossPageContextView.sample.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    cross_page_sample_js = response.read().decode("utf-8")
                    cross_page_sample_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/crossPageContextView.settings.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    cross_page_settings_js = response.read().decode("utf-8")
                    cross_page_settings_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/crossPageContextView.sampleValidation.worksheet.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    cross_page_sample_validation_worksheet_js = response.read().decode("utf-8")
                    cross_page_sample_validation_worksheet_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/crossPageContextView.sampleValidation.runbook.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    cross_page_sample_validation_runbook_js = response.read().decode("utf-8")
                    cross_page_sample_validation_runbook_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/crossPageContextView.sampleValidation.records.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    cross_page_sample_validation_records_js = response.read().decode("utf-8")
                    cross_page_sample_validation_records_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/crossPageContextView.sampleValidation.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    cross_page_sample_validation_parent_js = response.read().decode("utf-8")
                    cross_page_sample_validation_content_type = response.headers.get("Content-Type", "")
                cross_page_sample_validation_js = "\n".join((
                    cross_page_sample_validation_worksheet_js,
                    cross_page_sample_validation_runbook_js,
                    cross_page_sample_validation_records_js,
                    cross_page_sample_validation_parent_js,
                ))
                with urlopen(f"{server.url}/assets/crossPageContextView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    cross_page_context_view_js = response.read().decode("utf-8")
                    cross_page_context_view_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/renameLabels.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    rename_labels_js = response.read().decode("utf-8")
                    rename_labels_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/renameHistoryView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    rename_history_view_js = response.read().decode("utf-8")
                    rename_history_view_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/rename/preview.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    rename_preview_js = response.read().decode("utf-8")
                    rename_preview_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/rename/applyReadiness.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    rename_apply_readiness_js = response.read().decode("utf-8")
                    rename_apply_readiness_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/rename/applyResult.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    rename_apply_result_js = response.read().decode("utf-8")
                    rename_apply_result_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/renameView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    rename_view_parent_js = response.read().decode("utf-8")
                    rename_view_content_type = response.headers.get("Content-Type", "")
                rename_view_js = "\n".join((
                    rename_preview_js,
                    rename_apply_readiness_js,
                    rename_apply_result_js,
                    rename_view_parent_js,
                ))
                with urlopen(f"{server.url}/assets/settingsOverview.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_overview_js = response.read().decode("utf-8")
                    settings_overview_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settingsCommandHistory.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_command_history_js = response.read().decode("utf-8")
                    settings_command_history_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settingsMetadata.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_metadata_js = response.read().decode("utf-8")
                    settings_metadata_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settings/metadataFields.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_metadata_fields_js = response.read().decode("utf-8")
                    settings_metadata_fields_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settings/builderControls.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_builder_controls_js = response.read().decode("utf-8")
                    settings_builder_controls_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settingsView.builders.audio.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_view_audio_builder_js = response.read().decode("utf-8")
                    settings_view_audio_builder_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settingsView.builders.video.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_view_video_builder_js = response.read().decode("utf-8")
                    settings_view_video_builder_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settingsView.builders.subtitle.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_view_subtitle_builder_js = response.read().decode("utf-8")
                    settings_view_subtitle_builder_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settingsView.builders.queue.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_view_queue_builder_js = response.read().decode("utf-8")
                    settings_view_queue_builder_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settingsView.builders.runtime.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_view_runtime_builder_js = response.read().decode("utf-8")
                    settings_view_runtime_builder_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settingsView.builders.file_safety.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_view_file_safety_builder_js = response.read().decode("utf-8")
                    settings_view_file_safety_builder_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settingsView.builders.pending.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_view_pending_builder_js = response.read().decode("utf-8")
                    settings_view_pending_builder_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settingsView.builders.network.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_view_network_builder_js = response.read().decode("utf-8")
                    settings_view_network_builder_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settingsView.rawTriage.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_view_raw_triage_js = response.read().decode("utf-8")
                    settings_view_raw_triage_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settingsView.safetyLocks.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_view_safety_locks_js = response.read().decode("utf-8")
                    settings_view_safety_locks_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settings/backendResult.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_backend_result_js = response.read().decode("utf-8")
                    settings_backend_result_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settings/patchReview.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_patch_review_js = response.read().decode("utf-8")
                    settings_patch_review_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settings/policyImpact.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_policy_impact_js = response.read().decode("utf-8")
                    settings_policy_impact_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/settingsView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    settings_view_parent_js = response.read().decode("utf-8")
                    settings_view_content_type = response.headers.get("Content-Type", "")
                settings_view_js = "\n".join((
                    settings_metadata_fields_js,
                    settings_builder_controls_js,
                    settings_view_raw_triage_js,
                    settings_view_safety_locks_js,
                    settings_backend_result_js,
                    settings_patch_review_js,
                    settings_policy_impact_js,
                    settings_view_parent_js,
                ))
                with urlopen(f"{server.url}/assets/networkView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    network_view_js = response.read().decode("utf-8")
                    network_view_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/diagnosticsTailView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    diagnostics_tail_view_js = response.read().decode("utf-8")
                    diagnostics_tail_view_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/diagnosticsStateSummaryView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    diagnostics_state_summary_view_js = response.read().decode("utf-8")
                    diagnostics_state_summary_view_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/diagnosticsView.activejobs.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    diagnostics_view_active_jobs_js = response.read().decode("utf-8")
                    diagnostics_view_active_jobs_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/diagnosticsView.log.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    diagnostics_view_log_js = response.read().decode("utf-8")
                    diagnostics_view_log_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/diagnosticsView.investigation.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    diagnostics_view_investigation_js = response.read().decode("utf-8")
                    diagnostics_view_investigation_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/diagnosticsView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    diagnostics_view_parent_js = response.read().decode("utf-8")
                    diagnostics_view_content_type = response.headers.get("Content-Type", "")
                diagnostics_view_js = "\n".join((
                    diagnostics_view_active_jobs_js,
                    diagnostics_view_log_js,
                    diagnostics_view_investigation_js,
                    diagnostics_view_parent_js,
                ))
                with urlopen(f"{server.url}/assets/reportsView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    reports_view_js = response.read().decode("utf-8")
                    reports_view_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/scheduleView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    schedule_view_js = response.read().decode("utf-8")
                    schedule_view_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/maintenanceView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    maintenance_view_js = response.read().decode("utf-8")
                    maintenance_view_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/telemetryView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    telemetry_view_js = response.read().decode("utf-8")
                    telemetry_view_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/progressView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    progress_view_js = response.read().decode("utf-8")
                    progress_view_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/launchReadinessView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    launch_readiness_view_js = response.read().decode("utf-8")
                    launch_readiness_view_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/launchHistoryView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    launch_history_view_js = response.read().decode("utf-8")
                    launch_history_view_content_type = response.headers.get("Content-Type", "")
                launch_view_risk_asset_paths = [
                    "assets/launch/risk/settingsAccess.js",
                    "assets/launch/risk/mediaPolicyValues.js",
                    "assets/launch/risk/riskRows.js",
                    "assets/launch/risk/policyPatch.js",
                    "assets/launch/risk/policyBoundary.js",
                ]
                launch_view_risk_parts = []
                launch_view_risk_child_content_types = {}
                for asset_path in launch_view_risk_asset_paths:
                    with urlopen(f"{server.url}/{asset_path}", timeout=5) as response:  # noqa: S310 - localhost test server
                        launch_view_risk_parts.append(response.read().decode("utf-8"))
                        launch_view_risk_child_content_types[asset_path] = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/launchView.risk.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    launch_view_risk_parts.append(response.read().decode("utf-8"))
                    launch_view_risk_content_type = response.headers.get("Content-Type", "")
                launch_view_risk_js = "\n".join(launch_view_risk_parts)
                with urlopen(f"{server.url}/assets/launchView.scope.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    launch_view_scope_js = response.read().decode("utf-8")
                    launch_view_scope_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/launchView.realmedia.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    launch_view_realmedia_js = response.read().decode("utf-8")
                    launch_view_realmedia_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/launchView.preflight.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    launch_view_preflight_js = response.read().decode("utf-8")
                    launch_view_preflight_content_type = response.headers.get("Content-Type", "")
                launch_view_child_asset_paths = [
                    "assets/launch/controllerState.js",
                    "assets/launch/statusRender.js",
                    "assets/launch/startRequest.js",
                    "assets/launch/scopeControls.js",
                    "assets/launch/commandButtons.js",
                ]
                launch_view_child_parts = []
                launch_view_child_content_types = {}
                for asset_path in launch_view_child_asset_paths:
                    with urlopen(f"{server.url}/{asset_path}", timeout=5) as response:  # noqa: S310 - localhost test server
                        launch_view_child_parts.append(response.read().decode("utf-8"))
                        launch_view_child_content_types[asset_path] = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/launchView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    launch_view_parent_js = response.read().decode("utf-8")
                    launch_view_content_type = response.headers.get("Content-Type", "")
                launch_view_js = "\n".join([*launch_view_child_parts, launch_view_parent_js])
                with urlopen(f"{server.url}/assets/contractView.js", timeout=5) as response:  # noqa: S310 - localhost test server
                    contract_view_js = response.read().decode("utf-8")
                    contract_view_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/styles.css", timeout=5) as response:  # noqa: S310 - localhost test server
                    css = response.read().decode("utf-8")
                    css_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/styles.tokens.css", timeout=5) as response:  # noqa: S310 - localhost test server
                    css_tokens = response.read().decode("utf-8")
                    css_tokens_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/styles.theme.css", timeout=5) as response:  # noqa: S310 - localhost test server
                    css_theme = response.read().decode("utf-8")
                    css_theme_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/styles.layout.css", timeout=5) as response:  # noqa: S310 - localhost test server
                    css_layout = response.read().decode("utf-8")
                    css_layout_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/styles.components.css", timeout=5) as response:  # noqa: S310 - localhost test server
                    css_components = response.read().decode("utf-8")
                    css_components_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/styles.pages.css", timeout=5) as response:  # noqa: S310 - localhost test server
                    css_pages = response.read().decode("utf-8")
                    css_pages_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/styles.controls.css", timeout=5) as response:  # noqa: S310 - localhost test server
                    css_controls = response.read().decode("utf-8")
                    css_controls_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/styles.layout-manager.css", timeout=5) as response:  # noqa: S310 - localhost test server
                    css_layout_manager = response.read().decode("utf-8")
                    css_layout_manager_content_type = response.headers.get("Content-Type", "")
                with urlopen(f"{server.url}/assets/styles.queue.css", timeout=5) as response:  # noqa: S310 - localhost test server
                    css_queue = response.read().decode("utf-8")
                    css_queue_content_type = response.headers.get("Content-Type", "")
            finally:
                server.stop()

        css_split_assets = "\n".join(
            [
                css_layout,
                css_components,
                css_pages,
                css_controls,
                css_layout_manager,
                css_queue,
            ]
        )
        queue_view_parent_js = queue_view_js
        queue_view_js = "\n".join([
            queue_view_summary_js,
            queue_view_review_js,
            queue_view_detail_js,
            queue_view_launch_js,
            queue_view_selection_js,
            queue_view_open_actions_js,
            queue_view_table_js,
            queue_view_parent_js,
        ])

        self.assertIn("text/html", content_type)
        bootstrap_match = re.search(
            r'<script type="application/json" id="media-pipeline-bootstrap">(.+?)</script>',
            html,
        )
        self.assertIsNotNone(bootstrap_match)
        bootstrap = json.loads(bootstrap_match.group(1))
        self.assertEqual(bootstrap["token"], "")
        self.assertEqual(bootstrap["tokenSource"], "http-only-cookie")
        self.assertIn("MediaPipelineAuth=", set_cookie)
        self.assertIn("HttpOnly", set_cookie)
        self.assertNotIn("window.MEDIA_PIPELINE_BOOTSTRAP", html)
        self.assertIn("createCrossPageSampleValidationModule", cross_page_context_view_js)
        self.assertIn("window.__crossPageSampleValidationModule", cross_page_sample_validation_js)
        self.assertNotIn("web-token", html)
        self.assertIn("/assets/apiClient.js", html)
        self.assertIn("/assets/dom/query.js", html)
        self.assertIn("/assets/dom/text.js", html)
        self.assertIn("/assets/dom/status.js", html)
        self.assertIn("/assets/dom/filtering.js", html)
        self.assertIn("/assets/dom/table.js", html)
        self.assertIn("/assets/domHelpers.js", html)
        self.assertIn("/assets/formatters.js", html)
        self.assertIn("/assets/commandHistory.js", html)
        self.assertIn("/assets/diagnosticsBridge.js", html)
        self.assertIn("/assets/completedView.evidence.js", html)
        self.assertIn("/assets/completedView.proof.js", html)
        self.assertIn("/assets/completedView.review.js", html)
        self.assertIn("/assets/completedView.diagnostics.js", html)
        self.assertIn("/assets/completedView.js", html)
        self.assertIn('id="completed-breakdown-status"', html)
        self.assertIn('id="completed-breakdown"', html)
        self.assertIn('id="completed-consistency-status"', html)
        self.assertIn('id="completed-consistency"', html)
        self.assertIn('id="completed-validation-status"', html)
        self.assertIn('id="completed-validation"', html)
        self.assertIn('id="completed-workflow-status"', html)
        self.assertIn('id="completed-workflow"', html)
        self.assertNotIn('id="completed-size-review-status"', html)
        self.assertNotIn('id="completed-size-review-summary"', html)
        self.assertNotIn('id="completed-size-review-rows"', html)
        self.assertIn('id="completed-size-evidence-status"', html)
        self.assertIn('id="completed-size-evidence-summary"', html)
        self.assertIn('id="completed-size-evidence-rows"', html)
        self.assertIn('id="completed-size-evidence-detail"', html)
        self.assertIn('id="completed-pending-proof-status"', html)
        self.assertIn('id="completed-pending-proof-summary"', html)
        self.assertIn('id="completed-pending-proof-rows"', html)
        self.assertIn('id="completed-pending-proof-detail"', html)
        self.assertIn('id="publish-reconciliation-status"', html)
        self.assertIn('id="publish-reconciliation-refresh-button"', html)
        self.assertIn('id="publish-reconciliation-summary"', html)
        self.assertIn('id="publish-reconciliation-rows"', html)
        self.assertIn('id="publish-reconciliation-detail"', html)
        self.assertIn("Publish Reconciliation", html)
        self.assertIn('id="completed-final-trust-status"', html)
        self.assertIn('id="completed-final-trust-summary"', html)
        self.assertIn('id="completed-final-trust-rows"', html)
        self.assertIn('id="completed-final-trust-detail"', html)
        self.assertIn('id="completed-pilot-evidence-status"', html)
        self.assertIn('id="completed-pilot-evidence-summary"', html)
        self.assertIn('id="completed-pilot-evidence-rows"', html)
        self.assertIn('id="completed-pilot-evidence-detail"', html)
        self.assertIn('id="completed-pilot-evidence-markdown"', html)
        self.assertIn('id="completed-output-acceptance-status"', html)
        self.assertIn('id="completed-output-acceptance-summary"', html)
        self.assertIn('id="completed-output-acceptance-rows"', html)
        self.assertIn('id="completed-output-acceptance-detail"', html)
        self.assertIn('id="completed-route-agreement-status"', html)
        self.assertIn('id="completed-route-agreement-summary"', html)
        self.assertIn('id="completed-route-agreement-rows"', html)
        self.assertIn('id="completed-route-agreement-detail"', html)
        self.assertIn("/assets/queueView.summary.js", html)
        self.assertIn("/assets/queueView.review.js", html)
        self.assertIn("/assets/queueView.detail.js", html)
        self.assertIn("/assets/queueView.launch.js", html)
        self.assertIn("/assets/queueView.js", html)
        self.assertIn("/assets/pendingPublishView.js", html)
        self.assertIn("/assets/crossPageContextView.conflict.js", html)
        self.assertIn("/assets/crossPageContextView.sample.js", html)
        self.assertIn("/assets/crossPageContextView.settings.js", html)
        self.assertIn("/assets/crossPageContextView.sampleValidation.worksheet.js", html)
        self.assertIn("/assets/crossPageContextView.sampleValidation.runbook.js", html)
        self.assertIn("/assets/crossPageContextView.sampleValidation.records.js", html)
        self.assertIn("/assets/crossPageContextView.sampleValidation.js", html)
        self.assertIn("/assets/crossPageContextView.js", html)
        self.assertIn('id="cross-page-context-status"', html)
        self.assertIn('id="cross-page-context-summary"', html)
        self.assertIn('id="cross-page-conflict-status"', html)
        self.assertIn('id="cross-page-conflict-rows"', html)
        self.assertIn('id="cross-page-sample-status"', html)
        self.assertIn('id="cross-page-sample-rows"', html)
        self.assertIn("Evidence Correlation", html)
        self.assertIn('id="cross-page-validation-template-status"', html)
        self.assertIn('id="cross-page-validation-template"', html)
        self.assertIn("Validation Template", html)
        self.assertIn('id="cross-page-real-media-status"', html)
        self.assertIn('id="cross-page-real-media-summary"', html)
        self.assertIn('id="cross-page-real-media-rows"', html)
        self.assertIn('id="cross-page-real-media-detail"', html)
        self.assertIn("Validation Worksheet", html)
        self.assertIn('data-cross-page-target="queue"', html)
        self.assertIn("/assets/pendingPublishView.recovery.js", html)
        self.assertIn("/assets/pendingPublishView.diagnostics.js", html)
        self.assertIn("/assets/pendingPublishView.drain.js", html)
        self.assertIn("/assets/pendingPublishView.confidence.js", html)
        self.assertIn('id="pending-risk-status"', html)
        self.assertIn('id="pending-risk"', html)
        self.assertIn('id="pending-validation-status"', html)
        self.assertIn('id="pending-validation"', html)
        self.assertIn('id="pending-workflow-status"', html)
        self.assertIn('id="pending-workflow"', html)
        self.assertIn('id="pending-evidence-status"', html)
        self.assertIn('id="pending-evidence-summary"', html)
        self.assertIn('id="pending-evidence-rows"', html)
        self.assertIn('id="pending-recovery-plan-rows"', html)
        self.assertIn('id="pending-recovery-plan-row-detail"', html)
        self.assertIn('id="pending-drain-correlation-status"', html)
        self.assertIn('id="pending-drain-correlation"', html)
        self.assertIn('id="pending-drain-confidence-status"', html)
        self.assertIn('id="pending-drain-confidence-summary"', html)
        self.assertIn('id="pending-drain-confidence-rows"', html)
        self.assertIn('id="pending-drain-decision-status"', html)
        self.assertIn('id="pending-drain-decision-summary"', html)
        self.assertIn('id="pending-drain-decision-rows"', html)
        self.assertIn('id="pending-drain-decision-detail"', html)
        self.assertIn('id="pending-post-drain-trust-status"', html)
        self.assertIn('id="pending-post-drain-trust-summary"', html)
        self.assertIn('id="pending-post-drain-trust-rows"', html)
        self.assertIn('id="pending-post-drain-trust-detail"', html)
        self.assertIn('id="pending-diagnostics-status"', html)
        self.assertIn('id="pending-diagnostics-guidance"', html)
        self.assertIn('id="pending-diagnostics-actions"', html)
        self.assertIn("/assets/renameLabels.js", html)
        self.assertIn("/assets/renameHistoryView.js", html)
        self.assertIn("/assets/renameView.js", html)
        self.assertIn("/assets/settingsOverview.js", html)
        self.assertIn("/assets/settingsCommandHistory.js", html)
        self.assertIn("/assets/settingsMetadata.js", html)
        self.assertIn("/assets/settings/metadataFields.js", html)
        self.assertIn("/assets/settings/builderControls.js", html)
        self.assertIn("/assets/settingsView.builders.audio.js", html)
        self.assertIn("/assets/settingsView.builders.video.js", html)
        self.assertIn("/assets/settingsView.builders.subtitle.js", html)
        self.assertIn("/assets/settingsView.builders.queue.js", html)
        self.assertIn("/assets/settingsView.builders.runtime.js", html)
        self.assertIn("/assets/settingsView.builders.file_safety.js", html)
        self.assertIn("/assets/settingsView.builders.pending.js", html)
        self.assertIn("/assets/settingsView.builders.network.js", html)
        self.assertIn("/assets/settingsView.rawTriage.js", html)
        self.assertIn("/assets/settingsView.safetyLocks.js", html)
        self.assertIn("/assets/settingsView.js", html)
        self.assertIn('id="settings-audio-auto-bitrate"', html)
        self.assertIn("/assets/networkView.js", html)
        self.assertIn("/assets/diagnosticsTailView.js", html)
        self.assertIn("/assets/diagnosticsStateSummaryView.js", html)
        self.assertIn("/assets/diagnosticsView.activejobs.js", html)
        self.assertIn("/assets/diagnosticsView.log.js", html)
        self.assertIn("/assets/diagnosticsView.investigation.js", html)
        self.assertIn("/assets/diagnosticsView.js", html)
        self.assertIn("/assets/reportsView.js", html)
        self.assertIn('id="report-audit-score-policy-status"', html)
        self.assertIn('id="report-audit-score-policy-save-button"', html)
        self.assertIn('id="report-audit-score-policy-reset-button"', html)
        self.assertIn('id="report-audit-ignore-selected-button"', html)
        self.assertIn('id="report-audit-export-rerun-csv-button"', html)
        self.assertIn('id="report-audit-export-detail"', html)
        self.assertIn("Advanced score controls", html)
        self.assertIn("Point issue", html)
        self.assertIn("High issue-code marker", html)
        self.assertIn("Medium issue-code marker", html)
        self.assertNotIn("High issue: <code>ffprobe-open-failed</code>", html)
        self.assertNotIn('data-audit-score-policy-mirror="high_issue"', html)
        self.assertIn("/assets/scheduleView.js", html)
        self.assertIn("/assets/maintenanceView.js", html)
        self.assertIn("/assets/telemetryView.js", html)
        self.assertIn("/assets/progressView.js", html)
        self.assertIn("/assets/launchReadinessView.js", html)
        self.assertIn("/assets/launchHistoryView.js", html)
        self.assertIn("/assets/launch/risk/settingsAccess.js", html)
        self.assertIn("/assets/launch/risk/mediaPolicyValues.js", html)
        self.assertIn("/assets/launch/risk/riskRows.js", html)
        self.assertIn("/assets/launch/risk/policyPatch.js", html)
        self.assertIn("/assets/launch/risk/policyBoundary.js", html)
        self.assertIn("/assets/launchView.risk.js", html)
        self.assertIn("/assets/launchView.scope.js", html)
        self.assertIn("/assets/launchView.realmedia.js", html)
        self.assertIn("/assets/launchView.preflight.js", html)
        self.assertIn("/assets/launch/controllerState.js", html)
        self.assertIn("/assets/launch/statusRender.js", html)
        self.assertIn("/assets/launch/startRequest.js", html)
        self.assertIn("/assets/launch/scopeControls.js", html)
        self.assertIn("/assets/launch/commandButtons.js", html)
        self.assertIn("/assets/launchView.js", html)
        self.assertIn('id="launch-settings-intent-status"', html)
        self.assertIn('id="launch-settings-intent-summary"', html)
        self.assertIn('id="launch-settings-intent-rows"', html)
        self.assertIn('id="launch-settings-intent-detail"', html)
        self.assertIn('id="launch-scope-reconciliation-status"', html)
        self.assertIn('id="launch-scope-reconciliation-summary"', html)
        self.assertIn('id="launch-scope-reconciliation-rows"', html)
        self.assertIn('id="launch-scope-reconciliation-detail"', html)
        self.assertIn('id="launch-start-decision-status"', html)
        self.assertIn('id="launch-start-decision-summary"', html)
        self.assertIn('id="launch-start-decision-rows"', html)
        self.assertIn('id="launch-start-decision-detail"', html)
        self.assertIn('id="launch-real-media-proof-status"', html)
        self.assertIn('id="launch-real-media-proof-summary"', html)
        self.assertIn('id="launch-real-media-proof-rows"', html)
        self.assertIn('id="launch-real-media-proof-detail"', html)
        self.assertIn('id="launch-sample-execution-status"', html)
        self.assertIn('id="launch-sample-execution-summary"', html)
        self.assertIn('id="launch-sample-execution-rows"', html)
        self.assertIn('id="launch-sample-execution-detail"', html)
        self.assertIn('id="launch-pilot-readiness-status"', html)
        self.assertIn('id="launch-pilot-readiness-summary"', html)
        self.assertIn('id="launch-pilot-readiness-rows"', html)
        self.assertIn('id="launch-pilot-readiness-detail"', html)
        self.assertIn('id="launch-backend-preflight-status"', html)
        self.assertIn('id="launch-backend-preflight-summary"', html)
        self.assertIn('id="launch-backend-preflight-rows"', html)
        self.assertIn('id="launch-backend-preflight-detail"', html)
        self.assertIn("/assets/contractView.js", html)
        self.assertIn("/assets/commandHistory/formatters.js", html)
        self.assertIn("/assets/commandHistory/diagnostics.js", html)
        self.assertLess(html.index("/assets/apiClient.js"), html.index("/assets/app.js"))
        self.assertLess(html.index("/assets/apiClient.js"), html.index("/assets/dom/query.js"))
        self.assertLess(html.index("/assets/dom/query.js"), html.index("/assets/dom/text.js"))
        self.assertLess(html.index("/assets/dom/text.js"), html.index("/assets/dom/status.js"))
        self.assertLess(html.index("/assets/dom/status.js"), html.index("/assets/dom/filtering.js"))
        self.assertLess(html.index("/assets/dom/filtering.js"), html.index("/assets/dom/table.js"))
        self.assertLess(html.index("/assets/dom/table.js"), html.index("/assets/domHelpers.js"))
        self.assertLess(html.index("/assets/domHelpers.js"), html.index("/assets/formatters.js"))
        self.assertLess(html.index("/assets/formatters.js"), html.index("/assets/progressView.js"))
        self.assertLess(html.index("/assets/progressView.js"), html.index("/assets/commandHistory/formatters.js"))
        self.assertLess(html.index("/assets/commandHistory/formatters.js"), html.index("/assets/commandHistory/diagnostics.js"))
        self.assertLess(html.index("/assets/commandHistory/diagnostics.js"), html.index("/assets/commandHistory.js"))
        self.assertLess(html.index("/assets/commandHistory.js"), html.index("/assets/diagnosticsBridge.js"))
        self.assertLess(html.index("/assets/diagnosticsBridge.js"), html.index("/assets/completed/evidence/commands.js"))
        self.assertLess(html.index("/assets/completed/evidence/commands.js"), html.index("/assets/completed/evidence/filterScope.js"))
        self.assertLess(html.index("/assets/completed/evidence/filterScope.js"), html.index("/assets/completed/evidence/acceptance.js"))
        self.assertLess(html.index("/assets/completed/evidence/acceptance.js"), html.index("/assets/completed/evidence/routeAgreement.js"))
        self.assertLess(html.index("/assets/completed/evidence/routeAgreement.js"), html.index("/assets/completedView.evidence.js"))
        self.assertLess(html.index("/assets/completedView.evidence.js"), html.index("/assets/completedView.proof.js"))
        self.assertLess(html.index("/assets/completedView.proof.js"), html.index("/assets/completed/review/integrity.js"))
        self.assertLess(html.index("/assets/completed/review/integrity.js"), html.index("/assets/completed/review/sizeReview.js"))
        self.assertLess(html.index("/assets/completed/review/sizeReview.js"), html.index("/assets/completed/review/healthSignals.js"))
        self.assertLess(html.index("/assets/completed/review/healthSignals.js"), html.index("/assets/completed/review/reviewRows.js"))
        self.assertLess(html.index("/assets/completed/review/reviewRows.js"), html.index("/assets/completed/review/investigationFilters.js"))
        self.assertLess(html.index("/assets/completed/review/investigationFilters.js"), html.index("/assets/completedView.review.js"))
        self.assertLess(html.index("/assets/completedView.review.js"), html.index("/assets/completedView.diagnostics.js"))
        self.assertLess(html.index("/assets/completedView.diagnostics.js"), html.index("/assets/completedView.js"))
        self.assertLess(html.index("/assets/completedView.js"), html.index("/assets/queueView.summary.js"))
        self.assertLess(html.index("/assets/queueView.summary.js"), html.index("/assets/queueView.review.js"))
        self.assertLess(html.index("/assets/queueView.review.js"), html.index("/assets/queueView.detail.js"))
        self.assertLess(html.index("/assets/queueView.detail.js"), html.index("/assets/queueView.launch.js"))
        self.assertLess(html.index("/assets/queueView.launch.js"), html.index("/assets/queueView.js"))
        self.assertLess(html.index("/assets/queueView.js"), html.index("/assets/pendingPublishView.recovery.js"))
        self.assertLess(html.index("/assets/pendingPublishView.recovery.js"), html.index("/assets/pendingPublishView.diagnostics.js"))
        self.assertLess(html.index("/assets/pendingPublishView.diagnostics.js"), html.index("/assets/pendingPublishView.drain.js"))
        self.assertLess(html.index("/assets/pendingPublishView.drain.js"), html.index("/assets/pendingPublishView.confidence.js"))
        self.assertLess(html.index("/assets/pendingPublishView.confidence.js"), html.index("/assets/pendingPublishView.js"))
        self.assertLess(html.index("/assets/pendingPublishView.js"), html.index("/assets/crossPageContextView.conflict.js"))
        self.assertLess(html.index("/assets/crossPageContextView.conflict.js"), html.index("/assets/crossPageContextView.sample.js"))
        self.assertLess(html.index("/assets/crossPageContextView.sample.js"), html.index("/assets/crossPageContextView.settings.js"))
        self.assertLess(html.index("/assets/crossPageContextView.settings.js"), html.index("/assets/crossPageContextView.sampleValidation.worksheet.js"))
        self.assertLess(html.index("/assets/crossPageContextView.sampleValidation.worksheet.js"), html.index("/assets/crossPageContextView.sampleValidation.runbook.js"))
        self.assertLess(html.index("/assets/crossPageContextView.sampleValidation.runbook.js"), html.index("/assets/crossPageContextView.sampleValidation.records.js"))
        self.assertLess(html.index("/assets/crossPageContextView.sampleValidation.records.js"), html.index("/assets/crossPageContextView.sampleValidation.js"))
        self.assertLess(html.index("/assets/crossPageContextView.sampleValidation.js"), html.index("/assets/crossPageContextView.js"))
        self.assertLess(html.index("/assets/crossPageContextView.js"), html.index("/assets/renameLabels.js"))
        self.assertLess(html.index("/assets/renameLabels.js"), html.index("/assets/renameHistoryView.js"))
        self.assertLess(html.index("/assets/renameHistoryView.js"), html.index("/assets/renameView.js"))
        self.assertLess(html.index("/assets/formatters.js"), html.index("/assets/settingsOverview.js"))
        self.assertLess(html.index("/assets/renameView.js"), html.index("/assets/settingsOverview.js"))
        self.assertLess(html.index("/assets/settingsOverview.js"), html.index("/assets/settingsCommandHistory.js"))
        self.assertLess(html.index("/assets/settingsCommandHistory.js"), html.index("/assets/settingsMetadata.js"))
        self.assertLess(html.index("/assets/settingsMetadata.js"), html.index("/assets/settings/metadataFields.js"))
        self.assertLess(html.index("/assets/settings/metadataFields.js"), html.index("/assets/settings/builderControls.js"))
        self.assertLess(html.index("/assets/settings/builderControls.js"), html.index("/assets/settingsView.builders.audio.js"))
        self.assertLess(html.index("/assets/settingsView.builders.audio.js"), html.index("/assets/settingsView.builders.video.js"))
        self.assertLess(html.index("/assets/settingsView.builders.video.js"), html.index("/assets/settingsView.builders.subtitle.js"))
        self.assertLess(html.index("/assets/settingsView.builders.subtitle.js"), html.index("/assets/settingsView.builders.queue.js"))
        self.assertLess(html.index("/assets/settingsView.builders.queue.js"), html.index("/assets/settingsView.builders.runtime.js"))
        self.assertLess(html.index("/assets/settingsView.builders.runtime.js"), html.index("/assets/settingsView.builders.file_safety.js"))
        self.assertLess(html.index("/assets/settingsView.builders.file_safety.js"), html.index("/assets/settingsView.builders.pending.js"))
        self.assertLess(html.index("/assets/settingsView.builders.pending.js"), html.index("/assets/settingsView.builders.network.js"))
        self.assertLess(html.index("/assets/settingsView.builders.network.js"), html.index("/assets/settingsView.rawTriage.js"))
        self.assertLess(html.index("/assets/settingsView.rawTriage.js"), html.index("/assets/settingsView.safetyLocks.js"))
        self.assertLess(html.index("/assets/settingsView.safetyLocks.js"), html.index("/assets/settingsView.js"))
        self.assertLess(html.index("/assets/settingsView.js"), html.index("/assets/networkView.js"))
        self.assertLess(html.index("/assets/networkView.js"), html.index("/assets/diagnosticsTailView.js"))
        self.assertLess(html.index("/assets/diagnosticsTailView.js"), html.index("/assets/diagnosticsStateSummaryView.js"))
        self.assertLess(html.index("/assets/diagnosticsStateSummaryView.js"), html.index("/assets/diagnosticsView.activejobs.js"))
        self.assertLess(html.index("/assets/diagnosticsView.activejobs.js"), html.index("/assets/diagnosticsView.log.js"))
        self.assertLess(html.index("/assets/diagnosticsView.log.js"), html.index("/assets/diagnosticsView.investigation.js"))
        self.assertLess(html.index("/assets/diagnosticsView.investigation.js"), html.index("/assets/diagnosticsView.js"))
        self.assertLess(html.index("/assets/diagnosticsView.js"), html.index("/assets/reportsView.js"))
        self.assertLess(html.index("/assets/reportsView.js"), html.index("/assets/scheduleView.js"))
        self.assertLess(html.index("/assets/scheduleView.js"), html.index("/assets/maintenanceView.js"))
        self.assertLess(html.index("/assets/maintenanceView.js"), html.index("/assets/telemetryView.js"))
        self.assertLess(html.index("/assets/telemetryView.js"), html.index("/assets/launchReadinessView.js"))
        self.assertLess(html.index("/assets/progressView.js"), html.index("/assets/launchReadinessView.js"))
        self.assertLess(html.index("/assets/launchReadinessView.js"), html.index("/assets/launchHistoryView.js"))
        self.assertLess(html.index("/assets/launchHistoryView.js"), html.index("/assets/launch/risk/settingsAccess.js"))
        self.assertLess(html.index("/assets/launch/risk/settingsAccess.js"), html.index("/assets/launch/risk/mediaPolicyValues.js"))
        self.assertLess(html.index("/assets/launch/risk/mediaPolicyValues.js"), html.index("/assets/launch/risk/riskRows.js"))
        self.assertLess(html.index("/assets/launch/risk/riskRows.js"), html.index("/assets/launch/risk/policyPatch.js"))
        self.assertLess(html.index("/assets/launch/risk/policyPatch.js"), html.index("/assets/launch/risk/policyBoundary.js"))
        self.assertLess(html.index("/assets/launch/risk/policyBoundary.js"), html.index("/assets/launchView.risk.js"))
        self.assertLess(html.index("/assets/launchView.risk.js"), html.index("/assets/launchView.scope.js"))
        self.assertLess(html.index("/assets/launchView.scope.js"), html.index("/assets/launchView.realmedia.js"))
        self.assertLess(html.index("/assets/launchView.realmedia.js"), html.index("/assets/launchView.preflight.js"))
        self.assertLess(html.index("/assets/launchView.preflight.js"), html.index("/assets/launch/controllerState.js"))
        self.assertLess(html.index("/assets/launch/controllerState.js"), html.index("/assets/launch/statusRender.js"))
        self.assertLess(html.index("/assets/launch/statusRender.js"), html.index("/assets/launch/startRequest.js"))
        self.assertLess(html.index("/assets/launch/startRequest.js"), html.index("/assets/launch/scopeControls.js"))
        self.assertLess(html.index("/assets/launch/scopeControls.js"), html.index("/assets/launch/commandButtons.js"))
        self.assertLess(html.index("/assets/launch/commandButtons.js"), html.index("/assets/launchView.js"))
        self.assertLess(html.index("/assets/launchView.js"), html.index("/assets/contractView.js"))
        self.assertLess(html.index("/assets/contractView.js"), html.index("/assets/app.js"))
        self.assertLess(html.index("/assets/commandHistory.js"), html.index("/assets/app.js"))
        self.assertLess(html.index("/assets/formatters.js"), html.index("/assets/app.js"))
        self.assertIn("api-contract", html)
        self.assertIn("api-contract-method", html)
        self.assertIn("api-contract-scope", html)
        self.assertIn("api-contract-filter", html)
        self.assertIn("api-contract-safety-status", html)
        self.assertIn("api-contract-safety-summary", html)
        self.assertIn("api-contract-safety-rows", html)
        self.assertIn("api-contract-safety-detail", html)
        self.assertIn("api-contract-rows", html)
        self.assertIn("api-contract-detail", html)
        self.assertIn("refresh-health", html)
        self.assertIn("close-readiness", html)
        self.assertIn('class="topbar-status"', html)
        self.assertIn("activity-primary", html)
        self.assertIn("activity-meta", html)
        self.assertIn("evidence-toggle", html)
        self.assertIn("home-readiness-status", html)
        self.assertIn("home-readiness-summary", html)
        self.assertIn("daily-driver-status", html)
        self.assertIn("daily-driver-summary", html)
        self.assertIn("daily-driver-rows", html)
        self.assertIn("daily-driver-legend", html)
        self.assertIn("home-next-queue-status", html)
        self.assertIn("home-next-queue-list", html)
        self.assertIn("Next 5 Videos", html)
        self.assertIn("home-settings-trust-status", html)
        self.assertIn("home-settings-trust-summary", html)
        self.assertIn("home-external-dependencies-status", html)
        self.assertIn("home-external-dependencies-summary", html)
        self.assertIn("home-active-work-status", html)
        self.assertIn("home-active-work-summary", html)
        self.assertIn("home-runtime-open-status", html)
        self.assertIn("Runtime Files", html)
        self.assertIn("The WebView never sends arbitrary filesystem paths.", html)
        self.assertIn("control-readiness-status", html)
        self.assertIn("control-readiness", html)
        self.assertIn("control-history", html)
        self.assertIn("progress-detail-rows", html)
        self.assertIn("progress-evidence-status", html)
        self.assertIn("progress-evidence-summary", html)
        self.assertIn("progress-evidence-rows", html)
        self.assertIn("progress-evidence-detail", html)
        self.assertIn("pipeline-event-rows", html)
        self.assertIn("gpu-rows", html)
        self.assertEqual(html.count('data-evidence-toggle-exempt="true"'), 0)
        self.assertIn("queue-filter", html)
        self.assertIn("queue-summary", html)
        self.assertIn("queue-readiness-status", html)
        self.assertIn("queue-readiness", html)
        self.assertIn("queue-breakdown-status", html)
        self.assertIn("queue-breakdown", html)
        self.assertIn("queue-validation-status", html)
        self.assertIn("queue-validation", html)
        self.assertIn("queue-workflow-status", html)
        self.assertIn("queue-workflow", html)
        self.assertIn("queue-backend-scope-status", html)
        self.assertIn("queue-backend-scope-summary", html)
        self.assertIn("queue-backend-scope-rows", html)
        self.assertIn("queue-launch-decision-status", html)
        self.assertIn("queue-launch-decision-summary", html)
        self.assertIn("queue-launch-decision-rows", html)
        self.assertIn("queue-launch-decision-detail", html)
        self.assertIn("queue-review-status", html)
        self.assertIn("queue-review-board", html)
        self.assertIn("queue-review-rows", html)
        self.assertIn("queue-review-legend", html)
        self.assertIn("queue-collision-status", html)
        self.assertIn("queue-collision", html)
        self.assertIn("queue-excluded-status", html)
        self.assertIn("queue-excluded-summary", html)
        self.assertIn("queue-excluded-rows", html)
        self.assertIn("queue-excluded-detail", html)
        self.assertIn("queue-excluded-open-status", html)
        self.assertIn('data-open-target-row-actions="queue-excluded"', html)
        self.assertIn('targetDataset: "openQueueExcluded"', js)
        self.assertIn("Open Excluded Source", js)
        self.assertIn("queue-detail", html)
        self.assertIn("queue-diagnostics-status", html)
        self.assertIn("queue-diagnostics-guidance", html)
        self.assertIn("queue-diagnostics-actions", html)
        self.assertIn("queue-open-status", html)
        self.assertIn("queue-open-history", html)
        self.assertIn('data-open-target-row-actions="queue"', html)
        self.assertIn('targetDataset: "openQueue"', js)
        self.assertIn("Open Source Root", js)
        self.assertIn('data-page-panel="completed"', html)
        self.assertIn("completed-filter", html)
        self.assertIn("completed-rows", html)
        self.assertIn("completed-history-filter", html)
        self.assertIn("completed-history-rows", html)
        self.assertIn("completed-refresh-current-output-button", html)
        self.assertIn("output-overview-section-current", html)
        self.assertIn("output-overview-section-history", html)
        self.assertIn("completed-summary", html)
        self.assertIn("completed-integrity-status", html)
        self.assertIn("completed-integrity", html)
        self.assertIn("completed-validation-status", html)
        self.assertIn("completed-validation", html)
        self.assertIn("completed-workflow-status", html)
        self.assertIn("completed-workflow", html)
        self.assertNotIn("completed-review-status", html)
        self.assertNotIn("completed-review-board", html)
        self.assertNotIn("completed-review-rows", html)
        self.assertNotIn("completed-review-legend", html)
        self.assertNotIn("completed-size-review-status", html)
        self.assertNotIn("completed-size-review-summary", html)
        self.assertNotIn("completed-size-review-rows", html)
        self.assertIn("completed-size-evidence-status", html)
        self.assertIn("completed-size-evidence-summary", html)
        self.assertIn("completed-size-evidence-rows", html)
        self.assertIn("completed-size-evidence-detail", html)
        self.assertIn("completed-pending-proof-status", html)
        self.assertIn("completed-pending-proof-summary", html)
        self.assertIn("completed-pending-proof-rows", html)
        self.assertIn("completed-pending-proof-detail", html)
        self.assertIn("publish-reconciliation-status", html)
        self.assertIn("publish-reconciliation-refresh-button", html)
        self.assertIn("publish-reconciliation-summary", html)
        self.assertIn("publish-reconciliation-rows", html)
        self.assertIn("publish-reconciliation-detail", html)
        self.assertIn("completed-final-trust-status", html)
        self.assertIn("completed-final-trust-summary", html)
        self.assertIn("completed-final-trust-rows", html)
        self.assertIn("completed-final-trust-detail", html)
        self.assertIn("completed-output-acceptance-status", html)
        self.assertIn("completed-output-acceptance-summary", html)
        self.assertIn("completed-output-acceptance-rows", html)
        self.assertIn("completed-output-acceptance-detail", html)
        self.assertIn("completed-route-agreement-status", html)
        self.assertIn("completed-route-agreement-summary", html)
        self.assertIn("completed-route-agreement-rows", html)
        self.assertIn("completed-route-agreement-detail", html)
        self.assertIn("completed-detail", html)
        self.assertIn("completed-diagnostics-status", html)
        self.assertIn("completed-diagnostics-guidance", html)
        self.assertIn("completed-diagnostics-actions", html)
        completed_page_start = html.index('data-page-panel="completed"')
        completed_page_end = html.find('data-page-panel="pending"', completed_page_start)
        completed_page_html = html[completed_page_start:completed_page_end if completed_page_end != -1 else len(html)]
        self.assertIn("completed-current-row-actions", completed_page_html)
        self.assertIn('data-open-target-row-actions="completed"', completed_page_html)
        self.assertLess(
            completed_page_html.index('id="completed-table-legend"'),
            completed_page_html.index('data-open-target-row-actions="completed"'),
        )
        self.assertLess(
            completed_page_html.index('data-open-target-row-actions="completed"'),
            completed_page_html.index("<h2>Why This Output Looks Different</h2>"),
        )
        self.assertLess(
            completed_page_html.index('id="completed-open-status"'),
            completed_page_html.index("<h2>Why This Output Looks Different</h2>"),
        )
        self.assertIn('targetDataset: "openCompleted"', js)
        self.assertIn("Play Output", js)
        self.assertIn("play_output_file", js)
        self.assertIn("Output review:", completed_view_review_js)
        self.assertIn("pending-rows", html)
        self.assertIn("pending-filter", html)
        self.assertIn("pending-drain-button", html)
        self.assertIn("pending-drain-status", html)
        self.assertIn("pending-drain-detail", html)
        self.assertIn("pending-drain-history", html)
        self.assertEqual(html.count('id="pending-drain-button"'), 1)
        self.assertLess(html.index('id="pending-drain-button"'), html.index('id="pending-status"'))
        self.assertLess(html.index('id="pending-drain-button"'), html.index('id="pending-rows"'))
        self.assertIn("pending-drain-events-status", html)
        self.assertIn("pending-drain-events", html)
        self.assertIn("pending-drain-summary-status", html)
        self.assertIn("pending-drain-summary", html)
        self.assertIn("pending-publish-readiness-status", html)
        self.assertIn("pending-publish-readiness", html)
        self.assertIn("pending-validation-status", html)
        self.assertIn("pending-validation", html)
        self.assertIn("pending-workflow-status", html)
        self.assertIn("pending-workflow", html)
        self.assertIn("pending-review-status", html)
        self.assertIn("pending-review-board", html)
        self.assertIn("pending-review-rows", html)
        self.assertIn("pending-review-legend", html)
        self.assertIn("pending-evidence-status", html)
        self.assertIn("pending-evidence-summary", html)
        self.assertIn("pending-evidence-rows", html)
        self.assertIn("pending-recovery-plan-rows", html)
        self.assertIn("pending-recovery-plan-row-detail", html)
        self.assertIn("pending-drain-correlation-status", html)
        self.assertIn("pending-drain-correlation", html)
        self.assertIn("pending-drain-confidence-status", html)
        self.assertIn("pending-drain-confidence-summary", html)
        self.assertIn("pending-drain-confidence-rows", html)
        self.assertIn("pending-drain-decision-status", html)
        self.assertIn("pending-drain-decision-summary", html)
        self.assertIn("pending-drain-decision-rows", html)
        self.assertIn("pending-drain-decision-detail", html)
        self.assertIn("pending-post-drain-trust-status", html)
        self.assertIn("pending-post-drain-trust-summary", html)
        self.assertIn("pending-post-drain-trust-rows", html)
        self.assertIn("pending-post-drain-trust-detail", html)
        self.assertIn("pending-detail", html)
        home_start = html.index('data-page-panel="home"')
        live_start = html.index('data-page-panel="live"')
        pending_start = html.index('data-page-panel="pending"')
        rename_start = html.index('data-page-panel="rename"')
        self.assertNotIn("pending-detail", html[home_start:live_start])
        self.assertIn("pending-detail", html[pending_start:rename_start])
        self.assertIn('data-page-panel="reports"', html)
        self.assertNotIn('data-reports-tab="overview"', html)
        self.assertNotIn('data-reports-tab-panel="overview"', html)
        self.assertIn('data-reports-tab="failures"', html)
        self.assertIn('data-reports-tab="audit"', html)
        self.assertIn('data-reports-tab="files"', html)
        self.assertIn('data-reports-tab-panel="failures"', html)
        self.assertIn('data-reports-tab-panel="audit"', html)
        self.assertIn('data-reports-tab-panel="files"', html)
        self.assertIn("report-triage-status", html)
        self.assertIn("report-triage", html)
        self.assertIn("report-investigation-status", html)
        self.assertIn("report-investigation-checklist", html)
        self.assertNotIn("Pre-Launch Context", html)
        self.assertNotIn("report-launch-handoff-status", html)
        self.assertNotIn("report-launch-handoff", html)
        self.assertNotIn("report-go-rerun-button", html)
        self.assertNotIn("report-go-audit-button", html)
        self.assertNotIn("report-go-diagnostics-button", html)
        self.assertNotIn("report-launch-handoff-action-status", html)
        self.assertIn("report-progress-status", html)
        self.assertIn("report-progress-bars", html)
        self.assertIn("report-progress-summary", html)
        self.assertIn("report-path-rows", html)
        self.assertIn("report-root-rows", html)
        self.assertIn("report-warning-status", html)
        self.assertIn("report-warning-rows", html)
        self.assertIn("failure-filter", html)
        self.assertIn("failure-source-markers", html)
        self.assertIn("failure-rows", html)
        self.assertIn("Suggested fix", html)
        self.assertIn("failure-summary", html)
        self.assertIn("failure-review-status", html)
        self.assertIn("failure-review-board", html)
        self.assertIn("failure-review-board-detail", html)
        self.assertIn("failure-detail", html)
        self.assertIn("failure-clear-status", html)
        self.assertIn("failure-clear-summary", html)
        self.assertIn("failure-preview-selected-clear-button", html)
        self.assertIn("failure-clear-selected-button", html)
        self.assertIn("failure-preview-visible-clear-button", html)
        self.assertIn("failure-clear-visible-button", html)
        self.assertIn("failure-preview-all-clear-button", html)
        self.assertIn("failure-clear-all-button", html)
        self.assertIn("Clear Selected", html)
        self.assertIn("Clear Visible", html)
        self.assertIn("Clear All", html)
        self.assertIn("audit-preview-filter", html)
        self.assertIn("audit-preview-priority-only", html)
        self.assertIn("audit-preview-rows", html)
        self.assertIn("audit-preview-summary", html)
        self.assertIn('data-reports-tab-panel="audit" data-panel-type="evidence"', html)
        self.assertIn("audit-review-status", html)
        self.assertIn("audit-review-board", html)
        self.assertIn("audit-preview-detail", html)
        self.assertIn('data-page-panel="schedule"', html)
        self.assertIn("schedule-day-rows", html)
        self.assertIn("schedule-summary", html)
        self.assertIn("schedule-guidance-status", html)
        self.assertIn("schedule-guidance", html)
        self.assertIn("schedule-timing-status", html)
        self.assertIn("schedule-timing", html)
        self.assertIn('data-page-panel="network"', html)
        self.assertIn("network-role", html)
        self.assertIn("network-readiness-status", html)
        self.assertIn("network-readiness-summary", html)
        self.assertIn('data-network-role-panel="coordinator"', html)
        self.assertIn('data-network-role-panel="worker"', html)
        self.assertIn("network-coordinator-overview-status", html)
        self.assertIn("network-coordinator-overview-summary", html)
        self.assertIn("network-coordinator-active-rows", html)
        self.assertIn("network-coordinator-queue-rows", html)
        self.assertIn("network-worker-overview-status", html)
        self.assertIn("network-worker-overview-summary", html)
        self.assertIn("network-worker-claim-rows", html)
        self.assertIn("network-worker-remote-queue-summary", html)
        self.assertIn("network-lifecycle-status", html)
        self.assertIn("network-lifecycle-summary", html)
        self.assertIn("network-lifecycle-rows", html)
        self.assertIn("network-lifecycle-legend", html)
        self.assertIn("network-lifecycle-detail", html)
        self.assertIn("network-evidence-status", html)
        self.assertIn("network-evidence-summary", html)
        self.assertIn("network-evidence-rows", html)
        self.assertIn("network-evidence-legend", html)
        self.assertIn("network-evidence-detail", html)
        self.assertIn("network-state-files-status", html)
        self.assertIn("network-state-files-summary", html)
        self.assertIn("network-state-files-rows", html)
        self.assertIn("network-state-files-legend", html)
        self.assertIn("network-state-files-detail", html)
        self.assertIn("network-open-history-status", html)
        self.assertIn("network-open-history", html)
        self.assertIn("network-worker-status", html)
        self.assertIn("network-worker-summary", html)
        self.assertIn("network-worker-progress-status", html)
        self.assertIn("network-worker-progress-bars", html)
        self.assertIn("network-worker-progress-summary", html)
        self.assertIn("network-worker-rows", html)
        self.assertIn("network-worker-detail", html)
        self.assertIn("network-worker-status-filter", html)
        self.assertIn("network-worker-filter", html)
        self.assertIn("Distributed Mode Settings", html)
        self.assertIn("settings-network-role", html)
        self.assertIn("settings-network-coordinator-port", html)
        self.assertIn("settings-network-worker-url", html)
        self.assertIn("settings-network-path-map", html)
        self.assertIn("settings-network-apply-button", html)
        self.assertIn("network-role-setup-dialog", html)
        self.assertIn("network-role-coordinator-setup-button", html)
        self.assertIn("network-role-worker-setup-button", html)
        self.assertIn("network-settings-preview-button", html)
        self.assertIn("network-settings-save-button", html)
        self.assertIn("network-settings-patch-handoff", html)
        self.assertIn("network-settings-rows", html)
        self.assertIn("network-api-summary", html)
        self.assertIn('data-page-panel="maintenance"', html)
        self.assertIn("maintenance-refresh-button", html)
        self.assertIn("maintenance-progress-status", html)
        self.assertIn("maintenance-progress-bars", html)
        self.assertIn("maintenance-progress-steps", html)
        self.assertIn("maintenance-rows", html)
        self.assertIn("maintenance-readiness-status", html)
        self.assertIn("maintenance-readiness", html)
        self.assertIn("maintenance-toolchain-status", html)
        self.assertIn("maintenance-toolchain", html)
        self.assertIn("maintenance-warnings", html)
        self.assertIn("maintenance-table-legend", html)
        self.assertIn("maintenance-detail-status", html)
        self.assertIn("maintenance-detail", html)
        self.assertIn("maintenance-diagnostics-actions", html)
        self.assertIn("maintenance-diagnostics-status", html)
        self.assertIn("maintenance-dry-run-confidence-status", html)
        self.assertIn("maintenance-dry-run-confidence", html)
        self.assertIn("release-dry-run-button", html)
        self.assertIn("release-build-button", html)
        self.assertIn("Preview Deployment", html)
        self.assertIn("Zip package", html)
        self.assertIn("Verify package", html)
        self.assertIn("Preview Deployment runs the release builder with DryRun", html)
        self.assertIn("release-build-force", html)
        self.assertIn("release-build-detail", html)
        self.assertIn("release-build-progress-bars", html)
        self.assertIn("release-package-status-strip", html)
        self.assertIn("release-dry-run-state-value", html)
        self.assertIn("release-build-state-value", html)
        self.assertIn("release-dry-run-detail", html)
        self.assertIn("release-dry-run-progress-bars", html)
        self.assertIn("release-dry-run-optional-tools", html)
        self.assertIn("backfill-dry-run-progress-bars", html)
        self.assertIn("backfill-dry-run-button", html)
        self.assertIn("backfill-dry-run-detail", html)
        self.assertIn("dependency-atlas-button", html)
        self.assertIn("dependency-atlas-open-folder-button", html)
        self.assertIn("dependency-atlas-status", html)
        self.assertIn("dependency-atlas-progress-bars", html)
        self.assertIn("dependency-atlas-detail", html)
        self.assertIn("maintenance-dry-run-history-status", html)
        self.assertIn("maintenance-dry-run-history", html)
        self.assertIn('data-page-panel="launch"', html)
        self.assertIn('data-launch-tab="readiness"', html)
        self.assertIn('data-launch-tab="pipeline"', html)
        self.assertNotIn('data-launch-tab="audit"', html)
        self.assertIn('data-launch-tab="rerun"', html)
        self.assertIn('data-launch-tab="history"', html)
        launch_tab_order = [
            'data-launch-tab="pipeline"',
            'data-launch-tab="rerun"',
            'data-launch-tab="history"',
            'data-launch-tab="readiness"',
        ]
        prior_index = -1
        for launch_tab in launch_tab_order:
            current_index = html.index(launch_tab)
            self.assertGreater(current_index, prior_index)
            prior_index = current_index
        self.assertEqual(html.count('id="pipeline-start-button"'), 1)
        self.assertLess(html.index('id="pipeline-start-show-console"'), html.index('id="pipeline-start-button"'))
        self.assertLess(html.index('id="pipeline-start-button"'), html.index('id="launch-start-decision-status"'))
        self.assertIn('data-launch-tab-panel="readiness"', html)
        self.assertIn('data-launch-tab-panel="pipeline"', html)
        self.assertNotIn('data-launch-tab-panel="audit"', html)
        self.assertIn('data-launch-tab-panel="rerun"', html)
        self.assertIn('data-launch-tab-panel="history"', html)
        self.assertIn("launch-readiness-status", html)
        self.assertIn("launch-readiness", html)
        self.assertIn("launch-timing-status", html)
        self.assertIn("launch-timing", html)
        self.assertIn("launch-settings-trust-status", html)
        self.assertIn("launch-settings-trust-summary", html)
        self.assertIn("launch-settings-risk-status", html)
        self.assertIn("launch-settings-risk-summary", html)
        self.assertIn("launch-settings-risk-rows", html)
        self.assertIn("launch-settings-risk-detail", html)
        self.assertIn("pipeline-start-mode", html)
        self.assertIn("pipeline-start-single-file", html)
        self.assertIn("pipeline-single-file-browse-button", html)
        self.assertIn("pipeline-single-file-clear-button", html)
        self.assertIn("pipeline-single-file-browse-status", html)
        self.assertIn("Advanced Controller", html)
        self.assertNotIn("Selected Mode", html)
        self.assertIn("pipeline-start-schedule-override", html)
        self.assertIn("Start Evidence", html)
        self.assertIn("pipeline-launch-preflight", html)
        self.assertIn("pipeline-start-button", html)
        self.assertNotIn('id="audit-start-library-root"', html)
        self.assertNotIn('id="audit-launch-preflight"', html)
        self.assertNotIn('id="audit-launch-progress-status"', html)
        self.assertNotIn('id="audit-launch-log-rows"', html)
        self.assertNotIn('id="audit-score-policy-save-button"', html)
        self.assertNotIn("High issue: <code>foreign-audio-no-text-subtitles</code>", html)
        self.assertNotIn('id="audit-ignore-selected-button"', html)
        self.assertNotIn('id="audit-export-rerun-csv-button"', html)
        self.assertNotIn('id="audit-start-button"', html)
        self.assertIn("rerun-start-csv-path", html)
        self.assertIn("rerun-launch-preflight", html)
        self.assertIn("rerun-start-button", html)
        self.assertIn("launch-history-status", html)
        self.assertIn("launch-history", html)
        self.assertIn("launch-command-review-status", html)
        self.assertIn("launch-command-review-summary", html)
        self.assertIn("launch-command-review-rows", html)
        self.assertIn("launch-command-review-legend", html)
        self.assertIn("launch-command-review-detail", html)
        self.assertIn("launch-command-diagnostics-guidance", html)
        self.assertIn("launch-command-diagnostics-actions", html)
        self.assertIn("Checklist Correlation", html)
        self.assertIn("command-rows", html)
        self.assertIn("command-summary", html)
        self.assertIn("command-detail", html)
        self.assertIn('<th scope="col">Owner</th>', html)
        self.assertIn('<th scope="col">Issue</th>', html)
        self.assertIn("settings-validate-button", html)
        self.assertIn("settings-trust-status", html)
        self.assertIn("settings-trust-summary", html)
        self.assertIn('data-confirm-command="true"', html)
        self.assertIn("settings-rename-remove-terms", html)
        self.assertIn("Rename Cleaning Filters", html)
        self.assertIn("Movie Filters", html)
        self.assertIn('data-rename-movie-filter="video_source"', html)
        self.assertIn('data-rename-movie-filter="languages_subs_dubs"', html)
        self.assertIn("settings-rename-filter-languages-subs-dubs", html)
        self.assertIn("rename-workbench", html)
        self.assertIn("Choose Files", html)
        self.assertIn("rename-stage-files-heading", html)
        self.assertIn("rename-file-source-status", html)
        self.assertIn("rename-file-source-summary", html)
        self.assertIn("rename-browse-files-button", html)
        self.assertIn("rename-browse-folder-button", html)
        self.assertIn("rename-clear-paths-button", html)
        self.assertIn("rename-drop-zone", html)
        self.assertIn("rename-stage-mode-heading", html)
        self.assertIn("rename-mode", html)
        self.assertIn("rename-force-pipeline", html)
        self.assertIn("rename-pipeline-preview", html)
        self.assertIn("rename-template-preset", html)
        self.assertIn("tv_no_episode_title", html)
        self.assertIn("Movie: Title (Year)", html)
        self.assertIn("rename-stage-preview-heading", html)
        self.assertIn("rename-preview-status", html)
        self.assertIn("rename-preview-button", html)
        self.assertIn("rename-rows", html)
        self.assertIn("rename-table-legend", html)
        self.assertIn("rename-apply-button", html)
        self.assertIn("rename-apply-status-hint", html)
        self.assertIn("rename-apply-readiness-status", html)
        self.assertIn("rename-apply-readiness-rows", html)
        self.assertIn("rename-apply-progress-bars", html)
        self.assertIn("rename-apply-outcome-status", html)
        self.assertIn("rename-apply-outcome-rows", html)
        self.assertIn("rename-apply-outcome-summary", html)
        self.assertIn("rename-summary", html)
        self.assertIn("rename-confirm-dialog", html)
        self.assertIn("rename-confirm-apply-button", html)
        self.assertIn("rename-result-dialog", html)
        self.assertIn("rename-result-open-log-button", html)
        self.assertIn("rename-last-apply-status", html)
        self.assertIn("rename-last-apply-detail", html)
        self.assertIn("rename-apply-history", html)
        queue_start = html.index('data-page-panel="queue"')
        completed_start = html.index('data-page-panel="completed"')
        launch_start = html.index('data-page-panel="launch"')
        self.assertNotIn("rename-apply-button", html[queue_start:completed_start])
        self.assertIn("rename-workbench", html[rename_start:launch_start])
        self.assertIn("rename-preview-button", html[rename_start:launch_start])
        self.assertIn("rename-apply-button", html[rename_start:launch_start])
        self.assertIn("rename-summary", html[rename_start:launch_start])
        self.assertIn("rename-apply-readiness-rows", html[rename_start:launch_start])
        self.assertIn("rename-apply-outcome-rows", html[rename_start:launch_start])
        self.assertIn("rename-result-dialog", html[rename_start:launch_start])
        self.assertIn("rename-browse-files-button", html[rename_start:launch_start])
        self.assertIn("rename-clear-paths-button", html[rename_start:launch_start])
        self.assertIn("log-tail", html)
        self.assertIn("launch-logs", html)
        self.assertIn("diagnostics-close-status", html)
        self.assertIn("diagnostics-close-readiness", html)
        self.assertIn("backend-lifecycle-status", html)
        self.assertIn("backend-lifecycle-summary", html)
        self.assertIn("backend-shutdown-button", html)
        self.assertIn("backend-shutdown-status", html)
        self.assertIn("backend-lifecycle-history", html)
        self.assertIn("diagnostics-triage-status", html)
        self.assertIn("diagnostics-triage-summary", html)
        self.assertIn("diagnostics-investigation-status", html)
        self.assertIn("diagnostics-investigation-trail", html)
        self.assertIn("diagnostics-investigation-actions", html)
        self.assertIn("diagnostics-owner-handoff-status", html)
        self.assertIn("diagnostics-owner-handoff", html)
        self.assertIn("diagnostics-owner-handoff-rows", html)
        self.assertIn("diagnostics-owner-handoff-detail", html)
        self.assertIn("diagnostics-owner-handoff-actions", html)
        self.assertIn("diagnostics-owner-handoff-nav-status", html)
        self.assertIn("diagnostics-drilldown-status", html)
        self.assertIn("diagnostics-drilldown-summary", html)
        self.assertIn("diagnostics-drilldown-actions", html)
        self.assertIn("diagnostics-state-summary-status", html)
        self.assertIn("diagnostics-state-summary", html)
        self.assertIn("diagnostics-state-recovery-status", html)
        self.assertIn("diagnostics-state-recovery", html)
        self.assertIn("diagnostics-state-triage-status", html)
        self.assertIn("diagnostics-state-triage-summary", html)
        self.assertIn("diagnostics-state-triage-rows", html)
        self.assertIn("diagnostics-state-triage-detail", html)
        self.assertIn("diagnostics-state-triage-actions", html)
        self.assertIn("diagnostics-state-summary-rows", html)
        self.assertIn("diagnostics-state-summary-detail", html)
        self.assertIn("diagnostics-state-summary-actions", html)
        self.assertIn("diagnostics-command-status", html)
        self.assertIn("diagnostics-command-history", html)
        self.assertIn("diagnostics-command-drilldown-status", html)
        self.assertIn("diagnostics-command-drilldown-summary", html)
        self.assertIn("diagnostics-command-drilldown-rows", html)
        self.assertIn("diagnostics-command-drilldown-detail", html)
        self.assertIn("diagnostics-command-drilldown-actions", html)
        self.assertIn("diagnostics-command-owner-status", html)
        self.assertIn("diagnostics-command-owner-summary", html)
        self.assertIn("diagnostics-command-owner-rows", html)
        self.assertIn("diagnostics-command-owner-legend", html)
        self.assertIn("diagnostics-command-evidence-status", html)
        self.assertIn("diagnostics-command-evidence-summary", html)
        self.assertIn("diagnostics-command-evidence-rows", html)
        self.assertIn("diagnostics-command-resolution-status", html)
        self.assertIn("diagnostics-command-resolution-summary", html)
        self.assertIn("diagnostics-command-resolution-rows", html)
        self.assertIn("diagnostics-command-resolution-detail", html)
        self.assertIn("diagnostics-command-resolution-legend", html)
        self.assertIn("diagnostics-progress-status", html)
        self.assertIn("diagnostics-progress-bars", html)
        self.assertIn("diagnostics-progress-rows", html)
        self.assertIn("diagnostics-progress-detail", html)
        self.assertIn("diagnostics-log-status", html)
        self.assertIn("diagnostics-log-filter", html)
        self.assertIn("diagnostics-log-severity", html)
        self.assertIn("diagnostics-log-guidance", html)
        self.assertIn("diagnostics-log-rows", html)
        self.assertIn("diagnostics-log-detail", html)
        self.assertIn("diagnostics-log-actions", html)
        self.assertIn("diagnostics-tail-status", html)
        self.assertIn("diagnostics-tail-target", html)
        self.assertIn("diagnostics-tail-max-bytes", html)
        self.assertIn("diagnostics-tail-refresh-button", html)
        self.assertIn("diagnostics-tail-detail", html)
        self.assertIn("diagnostics-tail-text", html)
        self.assertIn("active-job-detail-status", html)
        self.assertIn("active-job-detail-rows", html)
        self.assertIn("active-job-detail", html)
        self.assertIn("telemetry-readiness-status", html)
        self.assertIn("telemetry-readiness-summary", html)
        self.assertIn("diagnostics-open-status", html)
        self.assertIn('data-open-diagnostics="run_logs"', html)
        self.assertIn('data-open-diagnostics="cluster_log"', html)
        self.assertIn('data-open-diagnostics="last_stdout_log"', html)
        self.assertIn('data-open-diagnostics="last_stderr_log"', html)
        self.assertIn('data-open-diagnostics="config"', html)
        self.assertIn('data-open-diagnostics="pending_publish"', html)
        self.assertIn('data-open-diagnostics="active_jobs"', html)
        self.assertIn('data-open-diagnostics="queue_snapshot"', html)
        self.assertIn('data-open-diagnostics="completed_manifest"', html)
        self.assertIn('data-open-diagnostics="failed_markers"', html)
        self.assertIn('data-open-diagnostics="sample_validation_log"', html)
        self.assertIn('value="sample_validation_log"', html)
        self.assertIn("settings-filter", html)
        self.assertIn("settings-profiles", html)
        self.assertIn("settings-validation", html)
        self.assertIn("settings-overview-status", html)
        self.assertIn("settings-overview-rows", html)
        self.assertIn("settings-safety-lock-status", html)
        self.assertIn("settings-safety-lock-summary", html)
        self.assertIn("settings-safety-lock-rows", html)
        self.assertIn("settings-raw-triage-status", html)
        self.assertIn("settings-raw-triage", html)
        self.assertIn("settings-raw-triage-rows", html)
        self.assertIn("settings-raw-triage-legend", html)
        self.assertIn("settings-raw-triage-detail", html)
        self.assertIn("Advanced Key Plan", html)
        self.assertIn("settings-raw-action-plan-status", html)
        self.assertIn("settings-raw-action-plan-summary", html)
        self.assertIn("settings-raw-action-plan-rows", html)
        self.assertIn("settings-raw-action-plan-legend", html)
        self.assertIn("settings-raw-action-plan-detail", html)
        self.assertIn("settings-builder-routing-profile", html)
        self.assertIn("settings-builder-size-guard", html)
        self.assertIn("settings-builder-encode-tuning", html)
        self.assertIn("settings-builder-encode-ladder", html)
        self.assertIn("settings-builder-max-growth", html)
        self.assertIn("settings-builder-apply-button", html)
        self.assertIn("settings-builder-reset-button", html)
        self.assertIn("settings-builder-guidance", html)
        self.assertIn('option value="strict"', html)
        self.assertNotIn('option value="enforce"', html)
        self.assertIn("settings-video-preset", html)
        self.assertIn("settings-video-quality", html)
        self.assertIn("settings-video-h264-remux", html)
        self.assertIn("settings-video-h264-max-bitrate", html)
        self.assertIn("settings-video-remux-safe-codecs", html)
        self.assertIn("settings-video-cpu-quality", html)
        self.assertIn("settings-video-cpu-threads", html)
        self.assertIn("settings-video-extra-flags", html)
        self.assertIn("settings-video-apply-button", html)
        self.assertIn("settings-video-apply-hint", html)
        self.assertIn("backend owns routing, codec, container, and encoder policy", html)
        self.assertIn("settings-video-guidance", html)
        self.assertIn("settings-file-safety-source-movies", html)
        self.assertIn("settings-file-safety-source-tv", html)
        self.assertIn("settings-file-safety-outsource", html)
        self.assertIn("settings-file-safety-local-base", html)
        self.assertIn("settings-file-safety-valid-extensions", html)
        self.assertIn("settings-file-safety-robocopy-flags", html)
        self.assertIn("settings-file-safety-output-size-multiplier", html)
        self.assertIn("settings-file-safety-deferred-publish", html)
        self.assertIn("settings-file-safety-skip-stability", html)
        self.assertIn("settings-file-safety-enable-integrity", html)
        self.assertIn("settings-file-safety-aggressive-episode", html)
        self.assertIn("settings-file-safety-create-tv-subfolder", html)
        self.assertIn("settings-tv-library-folder-evidence", html)
        self.assertIn("settings-file-safety-apply-button", html)
        self.assertIn("settings-file-safety-guidance", html)
        self.assertIn("settings-pending-deferred-publish", html)
        self.assertIn("settings-pending-cleanup-remote", html)
        self.assertIn("settings-pending-transient-retry-limit", html)
        self.assertIn("settings-pending-robocopy-timeout", html)
        self.assertIn("settings-pending-robocopy-flags", html)
        self.assertIn("settings-pending-enable-integrity", html)
        self.assertIn("settings-pending-apply-button", html)
        self.assertIn("settings-pending-guidance", html)
        self.assertIn("settings-network-role", html)
        self.assertIn("settings-network-coordinator-port", html)
        self.assertIn("settings-network-worker-url", html)
        self.assertIn("settings-network-path-map", html)
        self.assertIn("settings-network-apply-button", html)
        self.assertIn("settings-network-guidance", html)
        self.assertIn("settings-queue-priority-markers", html)
        self.assertIn("settings-queue-processed-index-refresh", html)
        self.assertIn("settings-queue-min-pipeline-version", html)
        self.assertIn("settings-queue-reprocess-all", html)
        self.assertIn("settings-queue-apply-button", html)
        self.assertIn("settings-queue-guidance", html)
        self.assertIn("settings-runtime-debug-mode", html)
        self.assertIn("settings-runtime-console-log", html)
        self.assertIn("settings-runtime-log-retention", html)
        self.assertIn("settings-runtime-ffmpeg-encode-timeout", html)
        self.assertIn("settings-runtime-source-scan-interval", html)
        self.assertIn("settings-runtime-transient-retry-limit", html)
        self.assertIn("settings-runtime-apply-button", html)
        self.assertIn("settings-runtime-guidance", html)
        self.assertIn("settings-subtitle-languages", html)
        self.assertIn("settings-subtitle-convert-tx3g", html)
        self.assertIn("settings-subtitle-convert-bdpgs", html)
        self.assertIn("settings-subtitle-drop-ass", html)
        self.assertIn("settings-subtitle-bdpgs-path-status", html)
        self.assertIn("settings-subtitle-bdpgs-path-evidence", html)
        self.assertIn("settings-subtitle-apply-button", html)
        self.assertIn("settings-subtitle-guidance", html)
        self.assertIn("settings-audio-passthrough-profile", html)
        self.assertIn("settings-audio-compatible-codecs", html)
        self.assertIn("settings-audio-preferred-languages", html)
        self.assertIn("settings-audio-downmix-mode", html)
        self.assertIn("settings-audio-allow-no-audio", html)
        self.assertIn("settings-audio-apply-button", html)
        self.assertIn("settings-audio-guidance", html)
        self.assertIn("settings-media-policy-status", html)
        self.assertIn("settings-media-policy-summary", html)
        self.assertIn("settings-media-policy-rows", html)
        self.assertIn("settings-active-media-policy-status", html)
        self.assertIn("settings-active-media-policy-summary", html)
        self.assertIn("settings-active-media-policy-rows", html)
        self.assertIn("settings-reload-button", html)
        self.assertNotIn("settings-preview-patch-button", html)
        self.assertIn("settings-save-review-dialog", html)
        self.assertIn("settings-save-review-dialog-rows", html)
        self.assertIn("settings-save-patch-button", html)
        self.assertIn("settings-summarize-patch-button", html)
        self.assertIn("settings-patch-json", html)
        self.assertIn("settings-patch-detail", html)
        self.assertIn("settings-patch-impact-summary", html)
        self.assertIn("Save Candidate", html)
        self.assertIn("settings-policy-delta-status", html)
        self.assertIn("settings-policy-delta-summary", html)
        self.assertIn("settings-policy-delta-rows", html)
        self.assertIn("settings-policy-delta-legend", html)
        self.assertIn("Active Policy", html)
        self.assertIn("settings-effective-policy-status", html)
        self.assertIn("settings-effective-policy-summary", html)
        self.assertIn("settings-effective-policy-rows", html)
        self.assertIn("settings-effective-policy-legend", html)
        self.assertIn("settings-effective-policy-detail", html)
        self.assertIn("settings-save-readiness-status", html)
        self.assertIn("settings-save-readiness", html)
        self.assertIn("settings-save-review-rows", html)
        self.assertIn("settings-save-review-legend", html)
        self.assertIn("settings-save-review-detail", html)
        self.assertIn("settings-launch-impact-status", html)
        self.assertIn("settings-launch-impact-summary", html)
        self.assertIn("settings-launch-impact-rows", html)
        self.assertIn("settings-launch-impact-legend", html)
        self.assertIn("Save Result", html)
        self.assertIn("settings-backend-result-status", html)
        self.assertIn("settings-backend-result-summary", html)
        self.assertIn("settings-backend-result-rows", html)
        self.assertIn("settings-backend-result-legend", html)
        self.assertIn("settings-backend-result-detail", html)
        self.assertIn("settings-patch-summary-rows", html)
        self.assertIn("settings-patch-summary-status", html)
        self.assertIn("settings-patch-summary-changed-only", html)
        self.assertIn("settings-command-history-status", html)
        self.assertIn("settings-command-history", html)
        self.assertIn("completed-open-history", html)
        self.assertIn("pending-open-history", html)
        self.assertIn("diagnostics-open-history", html)
        self.assertIn("report-open-history-status", html)
        self.assertIn("report-open-history", html)
        self.assertIn("text/javascript", app_lifecycle_content_type)
        self.assertIn("text/javascript", app_topbar_content_type)
        self.assertIn("text/javascript", app_close_readiness_content_type)
        self.assertIn("text/javascript", app_tauri_lifecycle_content_type)
        self.assertIn("text/javascript", app_refresh_content_type)
        self.assertIn("text/javascript", app_home_content_type)
        self.assertIn("text/javascript", app_home_readiness_content_type)
        self.assertIn("text/javascript", app_row_open_actions_content_type)
        self.assertIn("text/javascript", js_content_type)
        self.assertIn("text/javascript", app_layout_manager_content_type)
        self.assertIn("text/javascript", api_client_content_type)
        for dom_asset_path, dom_content_type in dom_helper_child_content_types.items():
            self.assertIn("text/javascript", dom_content_type, dom_asset_path)
        self.assertIn("text/javascript", dom_helpers_content_type)
        self.assertIn("text/javascript", formatters_content_type)
        self.assertIn("text/javascript", command_history_content_type)
        self.assertIn("text/javascript", diagnostics_bridge_content_type)
        for evidence_asset_path, evidence_content_type in completed_view_evidence_child_content_types.items():
            self.assertIn("text/javascript", evidence_content_type, evidence_asset_path)
        self.assertIn("text/javascript", completed_view_evidence_content_type)
        self.assertIn("text/javascript", completed_view_proof_content_type)
        for review_asset_path, review_content_type in completed_view_review_child_content_types.items():
            self.assertIn("text/javascript", review_content_type, review_asset_path)
        self.assertIn("text/javascript", completed_view_review_content_type)
        self.assertIn("text/javascript", completed_view_diagnostics_content_type)
        self.assertIn("text/javascript", completed_view_status_boards_content_type)
        self.assertIn("text/javascript", completed_view_open_actions_content_type)
        self.assertIn("text/javascript", completed_view_selection_content_type)
        self.assertIn("text/javascript", completed_view_filters_content_type)
        self.assertIn("text/javascript", completed_view_table_content_type)
        self.assertIn("text/javascript", completed_view_content_type)
        self.assertIn("text/javascript", queue_view_summary_content_type)
        self.assertIn("text/javascript", queue_view_review_content_type)
        self.assertIn("text/javascript", queue_view_detail_content_type)
        self.assertIn("text/javascript", queue_view_launch_content_type)
        self.assertIn("text/javascript", queue_view_selection_content_type)
        self.assertIn("text/javascript", queue_view_open_actions_content_type)
        self.assertIn("text/javascript", queue_view_table_content_type)
        self.assertIn("text/javascript", queue_view_content_type)
        self.assertIn("text/javascript", pending_publish_summary_content_type)
        self.assertIn("text/javascript", pending_publish_details_content_type)
        self.assertIn("text/javascript", pending_publish_filters_content_type)
        self.assertIn("text/javascript", pending_publish_recovery_content_type)
        self.assertIn("text/javascript", pending_publish_diagnostics_content_type)
        self.assertIn("text/javascript", pending_publish_drain_content_type)
        self.assertIn("text/javascript", pending_publish_confidence_content_type)
        self.assertIn("text/javascript", pending_publish_view_content_type)
        self.assertIn("text/javascript", cross_page_conflict_content_type)
        self.assertIn("text/javascript", cross_page_sample_content_type)
        self.assertIn("text/javascript", cross_page_settings_content_type)
        self.assertIn("text/javascript", cross_page_sample_validation_worksheet_content_type)
        self.assertIn("text/javascript", cross_page_sample_validation_runbook_content_type)
        self.assertIn("text/javascript", cross_page_sample_validation_records_content_type)
        self.assertIn("text/javascript", cross_page_sample_validation_content_type)
        self.assertIn("text/javascript", cross_page_context_view_content_type)
        self.assertIn("text/javascript", rename_labels_content_type)
        self.assertIn("text/javascript", rename_history_view_content_type)
        self.assertIn("text/javascript", rename_preview_content_type)
        self.assertIn("text/javascript", rename_apply_readiness_content_type)
        self.assertIn("text/javascript", rename_apply_result_content_type)
        self.assertIn("text/javascript", rename_view_content_type)
        self.assertIn("text/javascript", settings_overview_content_type)
        self.assertIn("text/javascript", settings_command_history_content_type)
        self.assertIn("text/javascript", settings_metadata_content_type)
        self.assertIn("text/javascript", settings_metadata_fields_content_type)
        self.assertIn("text/javascript", settings_builder_controls_content_type)
        self.assertIn("text/javascript", settings_view_audio_builder_content_type)
        self.assertIn("text/javascript", settings_view_video_builder_content_type)
        self.assertIn("text/javascript", settings_view_subtitle_builder_content_type)
        self.assertIn("text/javascript", settings_view_queue_builder_content_type)
        self.assertIn("text/javascript", settings_view_runtime_builder_content_type)
        self.assertIn("text/javascript", settings_view_file_safety_builder_content_type)
        self.assertIn("text/javascript", settings_view_pending_builder_content_type)
        self.assertIn("text/javascript", settings_view_network_builder_content_type)
        self.assertIn("text/javascript", settings_view_raw_triage_content_type)
        self.assertIn("text/javascript", settings_view_safety_locks_content_type)
        self.assertIn("text/javascript", settings_backend_result_content_type)
        self.assertIn("text/javascript", settings_patch_review_content_type)
        self.assertIn("text/javascript", settings_policy_impact_content_type)
        self.assertIn("text/javascript", settings_view_content_type)
        self.assertIn("text/javascript", network_view_content_type)
        self.assertIn("text/javascript", diagnostics_tail_view_content_type)
        self.assertIn("text/javascript", diagnostics_state_summary_view_content_type)
        self.assertIn("text/javascript", diagnostics_view_active_jobs_content_type)
        self.assertIn("text/javascript", diagnostics_view_log_content_type)
        self.assertIn("text/javascript", diagnostics_view_investigation_content_type)
        self.assertIn("text/javascript", diagnostics_view_content_type)
        self.assertIn("text/javascript", reports_view_content_type)
        self.assertIn("text/javascript", schedule_view_content_type)
        self.assertIn("text/javascript", maintenance_view_content_type)
        self.assertIn("text/javascript", telemetry_view_content_type)
        self.assertIn("text/javascript", progress_view_content_type)
        self.assertIn("text/javascript", launch_readiness_view_content_type)
        self.assertIn("text/javascript", launch_history_view_content_type)
        for launch_risk_asset_path, launch_risk_child_content_type in launch_view_risk_child_content_types.items():
            self.assertIn("text/javascript", launch_risk_child_content_type, launch_risk_asset_path)
        self.assertIn("text/javascript", launch_view_risk_content_type)
        self.assertIn("text/javascript", launch_view_scope_content_type)
        self.assertIn("text/javascript", launch_view_realmedia_content_type)
        self.assertIn("text/javascript", launch_view_preflight_content_type)
        for launch_view_asset_path, launch_view_child_content_type in launch_view_child_content_types.items():
            self.assertIn("text/javascript", launch_view_child_content_type, launch_view_asset_path)
        self.assertIn("text/javascript", launch_view_content_type)
        self.assertIn("text/javascript", contract_view_content_type)
        self.assertIn("text/css", css_content_type)
        self.assertIn("text/css", css_tokens_content_type)
        self.assertIn("text/css", css_theme_content_type)
        self.assertIn("text/css", css_layout_content_type)
        self.assertIn("text/css", css_components_content_type)
        self.assertIn("text/css", css_pages_content_type)
        self.assertIn("text/css", css_controls_content_type)
        self.assertIn("text/css", css_layout_manager_content_type)
        self.assertIn("text/css", css_queue_content_type)
        self.assertIn('@import url("./styles.tokens.css");', css)
        self.assertIn('@import url("./styles.theme.css");', css)
        self.assertIn('@import url("./styles.layout.css");', css)
        self.assertIn('@import url("./styles.components.css");', css)
        self.assertIn('@import url("./styles.pages.css");', css)
        self.assertIn('@import url("./styles.controls.css");', css)
        self.assertIn('@import url("./styles.layout-manager.css");', css)
        self.assertIn('@import url("./styles.queue.css");', css)
        self.assertIn(":root {", css_tokens)
        self.assertIn("body.light-mode {", css_tokens)
        self.assertIn("body.light-mode .nav-button.is-active", css_theme)
        self.assertIn(".app-shell {", css_layout)
        self.assertIn(".metric-grid {", css_components)
        self.assertIn(".workflow-table {", css_components)
        self.assertIn(".home-next-queue-panel {", css_pages)
        self.assertIn(".settings-tab-bar {", css_pages)
        self.assertIn(".primary-button {", css_controls)
        self.assertIn(".status-chip {", css_controls)
        self.assertIn("#customize-layout-btn {", css_layout_manager)
        self.assertIn(".panel-customize-bar {", css_layout_manager)
        self.assertIn(".layout-editor-drawer {", css_layout_manager)
        self.assertIn(".layout-editor-panel-row {", css_layout_manager)
        self.assertIn(".layout-panel-preview {", css_layout_manager)
        self.assertIn(".layout-drag-hint {", css_layout_manager)
        self.assertIn(".panel-drag-hint-active .panel-customize-bar", css_layout_manager)
        self.assertIn(".priority-badge {", css_queue)
        self.assertIn(".queue-strategy-select {", css_queue)
        self.assertIn(".fo-drawer {", css_queue)
        self.assertIn("window.mediaPipelineApi", api_client_js)
        self.assertIn("async function apiGet", api_client_js)
        self.assertIn("async function apiPost", api_client_js)
        self.assertIn("Authorization", api_client_js)
        self.assertIn("DEFAULT_GET_TIMEOUT_MS", api_client_js)
        self.assertIn("fetchWithTimeout", api_client_js)
        self.assertIn("AbortController", api_client_js)
        self.assertIn("Request timed out after", api_client_js)
        self.assertIn("apiGet(path, options = {})", api_client_js)
        self.assertIn("apiPost(path, payload, options = {})", api_client_js)
        self.assertIn("timeoutValue(options.timeoutMs, DEFAULT_GET_TIMEOUT_MS)", api_client_js)
        self.assertIn("timeoutValue(options.timeoutMs, 0)", api_client_js)
        self.assertIn("const raw = await response.text()", api_client_js)
        self.assertIn("JSON.parse(raw)", api_client_js)
        self.assertIn('raw.trim().replace(/\\s+/g, " ").slice(0, 500)', api_client_js)
        self.assertIn("data.error || data.message || `HTTP ${response.status}`", api_client_js)
        self.assertNotIn("await response.json()", api_client_js)
        self.assertIn("window.mediaPipelineDom", dom_helpers_js)
        self.assertIn("function filterRows", dom_helpers_js)
        self.assertIn("function appendCells", dom_helpers_js)
        self.assertIn("window.mediaPipelineFormatters", formatters_js)
        self.assertIn("function formatMemoryMb", formatters_js)
        self.assertIn("function settingsValuesEqual", formatters_js)
        self.assertNotIn("window.formatPercent =", formatters_js)
        self.assertNotIn("window.formatMemoryMb =", formatters_js)
        self.assertNotIn("window.formatConfigValue =", formatters_js)
        self.assertNotIn("window.parseSettingsListText =", formatters_js)
        self.assertNotIn("window.formatSettingsListValue =", formatters_js)
        self.assertNotIn("window.shortenPath =", formatters_js)
        self.assertNotIn("window.settingsValuesEqual =", formatters_js)
        self.assertIn("window.mediaPipelineCommandHistory", command_history_js)
        self.assertIn("let commandHistory", command_history_js)
        self.assertIn("function appendCommandResult", command_history_js)
        self.assertIn("function renderCommandHistoryPayload", command_history_js)
        self.assertIn("function getCommandHistory", command_history_js)
        self.assertIn("function mergeCommandHistory", command_history_js)
        self.assertIn("function renderCommandSummary", command_history_js)
        self.assertIn("function renderCommandDetail", command_history_js)
        self.assertIn("function commandHistorySummaryLines", command_history_js)
        self.assertIn("function commandHistoryDetailLines", command_history_js)
        self.assertIn("function commandHistoryOwnerPage", command_history_js)
        self.assertIn("function commandHistoryIssueLevel", command_history_js)
        self.assertIn("function commandHistoryCompactEvidenceLine", command_history_js)
        self.assertIn("function commandHistoryDiagnosticLine", command_history_js)
        self.assertIn("function compactCommandHistoryEntries", command_history_js)
        self.assertIn("function compactCommandHistoryBlockText", command_history_js)
        self.assertIn("function renderCompactCommandHistoryBlock", command_history_js)
        self.assertIn("window.commandHistoryCompactEvidenceLine = commandHistoryCompactEvidenceLine", command_history_js)
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "renderCompactCommandHistoryBlock")
        _assert_namespace_export(self, command_history_js, "mediaPipelineCommandHistory", "commandHistoryDiagnosticLine")
        self.assertIn("function commandHistorySuggestedAction", command_history_js)
        self.assertIn('command === "backend.shutdown"', command_history_js)
        self.assertIn("Backend shutdown was requested.", command_history_js)
        self.assertIn("function commandHistoryIssueDigestLines", command_history_js)
        self.assertIn("function commandHistoryOwnerLiveStateSummary", command_history_js)
        self.assertIn("function commandHistoryOwnerLiveStateLines", command_history_js)
        self.assertIn("Owner page live state handoff:", command_history_js)
        self.assertIn("Owner page live state", command_history_js)
        self.assertIn("Compare cached owner-page state with command detail before retrying from the owning page.", command_history_js)
        self.assertIn("getLastQueueRows", command_history_js)
        self.assertIn("getLastCompletedRows", command_history_js)
        self.assertIn("getLastPendingPublishPayload", command_history_js)
        self.assertIn("function commandHistoryTraceLines", command_history_js)
        self.assertIn("function renderCommandResolutionChecklist", command_history_js)
        self.assertIn("function commandHistoryResolutionRows", command_history_js)
        self.assertIn("function commandHistoryResolutionStatusState", command_history_js)
        self.assertIn("Command failure resolution checklist:", command_history_js)
        self.assertIn("retry or repeat only from the owning page after command detail, refresh target, diagnostics tails, and owner state agree.", command_history_js)
        self.assertIn("Mutation guardrail: this checklist cannot retry, launch, drain, save, rename, repair, delete, publish, open arbitrary paths, or bypass backend validation.", command_history_js)
        self.assertIn("Command issue digest:", command_history_js)
        self.assertIn("Command trace:", command_history_js)
        self.assertIn("Owner page:", command_history_js)
        self.assertIn("Suggested next action:", command_history_js)
        self.assertIn("command history is read-only", command_history_js)
        self.assertIn("function selectCommandEntry", command_history_js)
        self.assertIn("Select a row to inspect backend message", command_history_js)
        self.assertIn("Local pending visibility:", command_history_js)
        self.assertIn("const launchHistoryView = window.mediaPipelineLaunchHistoryView || {}", command_history_js)
        self.assertIn("launchHistoryView.renderLaunchCommandHistory(commandHistory)", command_history_js)
        self.assertIn("renderPendingDrainHistory(commandHistory)", command_history_js)
        self.assertIn("renderPendingDrainDecisionChecklist(undefined, undefined, undefined, commandHistory)", command_history_js)
        self.assertIn("renderMaintenanceDryRunHistory(commandHistory)", command_history_js)
        self.assertIn("window.mediaPipelineSettingsCommandHistory?.renderSettingsCommandHistory?.(commandHistory)", command_history_js)
        self.assertIn("renderQueueOpenHistory(commandHistory)", command_history_js)
        self.assertIn("renderQueueLaunchDecisionChecklist(undefined, undefined, commandHistory)", command_history_js)
        self.assertIn("renderCompletedOpenHistory(commandHistory)", command_history_js)
        self.assertIn("renderPendingOpenHistory(commandHistory)", command_history_js)
        self.assertIn("renderDiagnosticsOpenHistory(commandHistory)", command_history_js)
        self.assertIn("window.mediaPipelineRenameHistoryView?.renderRenameApplyHistory?.(commandHistory)", command_history_js)
        self.assertNotIn("typeof renderRenameApplyHistory === \"function\"", command_history_js)
        self.assertIn("renderPipelineControlHistory(commandHistory)", command_history_js)
        self.assertIn("window.mediaPipelineReportsView?.renderReportOpenHistory?.(commandHistory)", command_history_js)
        self.assertNotIn("typeof renderReportOpenHistory === \"function\"", command_history_js)
        self.assertIn("window.mediaPipelineNetworkView?.renderNetworkOpenHistory?.(commandHistory)", command_history_js)
        self.assertIn("window.mediaPipelineNetworkView?.initNetworkViewEvents?.();", js)
        self.assertIn("function _storedOrderMatchesCurrentPanels", app_layout_manager_js)
        self.assertIn('page.dataset.layoutOrderStatus = "schema-reset"', app_layout_manager_js)
        self.assertIn("newly added panels appear at their authored default position", app_layout_manager_js)
        self.assertIn("function _showLayoutDragHint", app_layout_manager_js)
        self.assertIn("Still gated. Click Advanced to make this panel always visible.", app_layout_manager_js)
        self.assertIn("window.mediaPipelineCompletedView", completed_view_js)
        self.assertIn("function renderCompleted", completed_view_js)
        self.assertIn("function renderCompletedRowsImpl", completed_view_table_js)
        self.assertIn("renderCompletedRows = completedReviewNoop", completed_view_js)
        self.assertIn("function renderCompletedIntegrity", completed_view_review_js)
        self.assertIn("function renderCompletedBreakdown", completed_view_review_js)
        self.assertIn("function renderCompletedRuntime", completed_view_review_js)
        self.assertIn("function completedIntegrityStatus", completed_view_review_js)
        self.assertIn("function completedIntegrityLines", completed_view_review_js)
        self.assertIn("function completedBreakdownLines", completed_view_review_js)
        self.assertIn("function completedRuntimeLines", completed_view_review_js)
        self.assertIn("Run History", html)
        self.assertIn("function renderCompletedConsistency", completed_view_review_js)
        self.assertIn("function completedConsistencyStatus", completed_view_review_js)
        self.assertIn("function completedConsistencyLines", completed_view_review_js)
        self.assertIn("function renderCompletedValidation", completed_view_review_js)
        self.assertIn("function renderCompletedReviewBoard", completed_view_review_js)
        self.assertIn("function completedReviewBoardLines", completed_view_review_js)
        self.assertIn("Operator review board: Completed", completed_view_review_js)
        self.assertNotIn("completed-review-board", html)
        self.assertIn("function renderCompletedSizeReview", completed_view_review_js)
        self.assertIn("function completedSizeReviewRows", completed_view_review_js)
        self.assertIn("function completedSizeReviewLines", completed_view_review_js)
        self.assertIn("Size growth review board:", completed_view_review_js)
        self.assertNotIn("completed-size-review-summary", html)
        self.assertIn("function renderCompletedSizeEvidence", completed_view_review_js)
        self.assertIn("function completedSizeEvidenceRows", completed_view_review_js)
        self.assertIn("Size growth evidence handoff:", completed_view_review_js)
        self.assertIn("Size growth may be intentional for compatibility, subtitles, or audio normalization", completed_view_review_js)
        self.assertIn("exact full-path proof beats same-leaf review", completed_view_review_js)
        self.assertIn("completed-size-evidence-summary", html)
        self.assertIn("completed-size-evidence-detail", html)
        self.assertIn("function createCompletedEvidenceModule", completed_view_evidence_js)
        self.assertIn("window.__completedViewEvidenceModule", completed_view_evidence_js)
        self.assertIn("const completedEvidenceModule = window.__completedViewEvidenceModule || {}", completed_view_js)
        self.assertIn("delete window.__completedViewEvidenceModule", completed_view_js)
        self.assertIn("createCompletedEvidenceModule({", completed_view_js)
        self.assertIn("function createCompletedProofModule", completed_view_proof_js)
        self.assertIn("window.__completedViewProofModule", completed_view_proof_js)
        self.assertIn("const completedProofModule = window.__completedViewProofModule || {}", completed_view_js)
        self.assertIn("delete window.__completedViewProofModule", completed_view_js)
        self.assertIn("createCompletedProofModule({", completed_view_js)
        self.assertIn("function createCompletedReviewModule", completed_view_review_js)
        self.assertIn("window.__completedViewReviewModule", completed_view_review_js)
        self.assertIn("const completedReviewModule = window.__completedViewReviewModule || {}", completed_view_js)
        self.assertIn("delete window.__completedViewReviewModule", completed_view_js)
        self.assertIn("createCompletedReviewModule({", completed_view_js)
        self.assertIn("function renderCompletedPendingProof", completed_view_evidence_js)
        self.assertIn("function completedPendingProofRows", completed_view_evidence_js)
        self.assertIn("function completedPendingProofDetailLines", completed_view_evidence_js)
        self.assertIn("function selectCompletedPendingProofRow", completed_view_evidence_js)
        self.assertIn("function renderPublishReconciliation", completed_view_evidence_js)
        self.assertIn("function requestPublishReconciliation", completed_view_evidence_js)
        self.assertIn("function publishReconciliationRows", completed_view_evidence_js)
        self.assertIn("function publishReconciliationDetailLines", completed_view_evidence_js)
        self.assertIn("/api/publish-reconciliation?limit=250", completed_view_evidence_js)
        self.assertIn("Backend publish reconciliation row:", completed_view_evidence_js)
        self.assertIn("Mutation guardrail: this backend row", completed_view_evidence_js)
        self.assertIn("publishReconciliationRefreshButton.addEventListener(\"click\", () => window.mediaPipelineCompletedView?.requestPublishReconciliation?.())", js)
        self.assertIn("Completed-to-Pending output proof cross-check:", completed_view_evidence_js)
        self.assertIn("function completedProofRowMissingOutput", completed_view_evidence_js)
        self.assertIn("completed-missing-output-no-pending-proof", completed_view_evidence_js)
        self.assertIn("completed-missing-output-still-pending", completed_view_evidence_js)
        self.assertIn("completed-missing-output-with-drain-proof", completed_view_evidence_js)
        self.assertIn("function completedPendingProofIsFinalPlacementReviewSignal", completed_view_evidence_js)
        self.assertIn("Missing completed output with pending proof:", completed_view_evidence_js)
        self.assertIn("Missing completed output with drain proof:", completed_view_evidence_js)
        self.assertIn("Missing completed output without pending/drain proof:", completed_view_evidence_js)
        self.assertIn("Treat as final-placement conflict", completed_view_evidence_js)
        self.assertIn("an empty Pending Publish page is not proof that the file published.", completed_view_evidence_js)
        self.assertIn("Mutation guardrail: this cross-check is read-only", completed_view_evidence_js)
        self.assertIn("same-leaf matches are duplicate-title hints only", completed_view_evidence_js)
        self.assertIn("Mutation guardrail: this detail panel does not accept, repair, rerun, drain, cleanup, delete, publish, rewrite manifests, or touch media files.", completed_view_evidence_js)
        self.assertIn("function renderCompletedOutputAcceptance", completed_view_evidence_js)
        self.assertIn("function completedAcceptanceRows", completed_view_evidence_js)
        self.assertIn("Completed output acceptance readiness:", completed_view_evidence_js)
        self.assertIn("Daily-use handoff: Completed evidence supports an operator trust decision", completed_view_evidence_js)
        self.assertIn("Scope boundary: Current Output filters, Completed History filters", completed_view_evidence_js)
        self.assertIn("readiness requires display filter scope, output/sidecar proof, route/size explanation, pending-publish proof, and recent command evidence to agree.", completed_view_evidence_js)
        self.assertIn("Mutation guardrail: this checklist does not accept, delete, rerun, reprocess, drain, cleanup, write manifests, or change policy.", completed_view_evidence_js)
        self.assertIn("Media And Route Proof", html)
        self.assertIn("function renderCompletedRealMediaProof", completed_view_proof_js)
        self.assertIn("function completedRealMediaProofRows", completed_view_proof_js)
        self.assertIn("function completedRealMediaProofSummaryLines", completed_view_proof_js)
        self.assertNotIn("function completedRealMediaProofRows", completed_view_js)
        self.assertIn("Real-media output proof ladder:", completed_view_proof_js)
        self.assertIn("Decision rule: output proof, sidecar proof, route/size/media decision, pending/drain posture, and diagnostics/runtime evidence must agree before trusting a sample.", completed_view_proof_js)
        self.assertIn("function completedPolicyAlignmentOutputEvidence", completed_view_proof_js)
        self.assertIn("Saved policy reconciliation", completed_view_proof_js)
        self.assertIn("Completed policy reconciliation:", completed_view_proof_js)
        self.assertIn("Post-run boundary: Completed can prove output-side evidence only", completed_view_proof_js)
        self.assertIn("Sample validation handoff", completed_view_proof_js)
        self.assertIn("Sample Validation handoff is evidence-only.", completed_view_proof_js)
        self.assertIn("Home Sample Validation can write JSONL evidence notes only", completed_view_proof_js)
        self.assertIn("function completedSampleValidationComparisonLines", completed_view_review_js)
        self.assertIn("Sample Validation comparison for selected Completed row:", completed_view_review_js)
        self.assertIn("Post-run capture: Preview Record now includes a copyable route/output/log/publish/subtitle/audio/size checklist", completed_view_review_js)
        self.assertIn("Output Verification", html)
        self.assertIn("function renderCompletedFinalTrust", completed_view_proof_js)
        self.assertIn("function completedFinalTrustRows", completed_view_proof_js)
        self.assertIn("function selectCompletedFinalTrustStep", completed_view_proof_js)
        self.assertIn("window.selectCompletedFinalTrustStep = selectCompletedFinalTrustStep", completed_view_js)
        self.assertIn("Completed final output trust walkthrough:", completed_view_proof_js)
        self.assertIn("trust the selected output only after Completed Manifest, disk/sidecar state, Pending Publish/drain proof, Plex/media policy evidence, Diagnostics logs, and Sample Validation preview agree.", completed_view_proof_js)
        self.assertIn("Manual playback/subtitle/audio/size inspection remains required before acceptance.", completed_view_proof_js)
        self.assertIn("renderCompletedFinalTrust(undefined, undefined, undefined, undefined, commandHistory)", command_history_js)
        self.assertIn("Evidence Packet", html)
        self.assertIn("function renderCompletedPilotEvidencePacket", completed_view_proof_js)
        self.assertIn("function completedPilotEvidencePacketRows", completed_view_proof_js)
        self.assertIn("Selected pilot evidence packet:", completed_view_proof_js)
        self.assertIn("Purpose: copyable post-run proof for a selected Completed row after a real-media pilot run.", completed_view_proof_js)
        self.assertIn("3b. Saved policy reconciliation", completed_view_proof_js)
        self.assertIn("do not append an accepted Sample Validation record until output, sidecar, route/size/media, pending/final placement, diagnostics, and manual playback checks agree.", completed_view_proof_js)
        self.assertIn("window.renderCompletedPilotEvidencePacket = renderCompletedPilotEvidencePacket", completed_view_js)
        self.assertIn("renderCompletedPilotEvidencePacket(undefined, undefined, undefined, undefined, commandHistory)", command_history_js)
        self.assertIn("window.renderCompletedPilotEvidencePacket(", pending_publish_view_js)
        self.assertIn("window.renderCompletedRealMediaProof(", pending_publish_view_js)
        self.assertIn("window.getLastCompletedPendingProofRows()", pending_publish_view_js)
        self.assertIn("renderCompletedOutputAcceptance(undefined, undefined, undefined, commandHistory)", command_history_js)
        self.assertIn("completed-output-acceptance-summary", html)
        self.assertIn("completed-output-acceptance-detail", html)
        self.assertIn("function completedCurrentFilterScope", completed_view_evidence_js)
        self.assertIn("function completedFilterScopeDetailLines", completed_view_evidence_js)
        self.assertIn("Display filter / backend action scope", completed_view_evidence_js)
        self.assertIn("Current Output display filter / backend action scope:", completed_view_evidence_js)
        self.assertIn("Backend action scope: unchanged.", completed_view_evidence_js)
        self.assertIn("Current Output filters never accept outputs", completed_view_evidence_js)
        self.assertIn("renderCompletedOutputAcceptance(payload, rows", completed_view_js)
        self.assertIn("ctx.renderCompletedOutputAcceptance(ctx.state.lastCompletedPayload, lastCompletedRows", completed_view_table_js)
        self.assertIn("readiness requires display filter scope, output/sidecar proof", completed_view_evidence_js)
        self.assertIn("Route Agreement", html)
        self.assertIn("function renderCompletedRouteAgreement", completed_view_evidence_js)
        self.assertIn("function completedRouteAgreementRows", completed_view_evidence_js)
        self.assertIn("function completedRouteAgreementStatus", completed_view_evidence_js)
        self.assertIn("function completedRouteAgreementRouteToken", completed_view_evidence_js)
        self.assertIn("Queue / Completed route agreement:", completed_view_evidence_js)
        self.assertIn("Completed source still queued", completed_view_evidence_js)
        self.assertIn("Route mismatch", completed_view_evidence_js)
        self.assertIn("a completed source should not appear runnable in Queue unless this is deliberate reprocess", completed_view_evidence_js)
        self.assertIn("typeof window.getLastQueuePayload === \"function\" ? window.getLastQueuePayload() : {}", completed_view_evidence_js)
        self.assertIn("Mutation guardrail: this agreement panel does not launch, rerun, drain, repair, reconcile, delete, rewrite manifests, or touch media files.", completed_view_evidence_js)
        self.assertIn("completed-route-agreement-summary", html)
        self.assertIn("completed-route-agreement-detail", html)
        self.assertIn("function getLastCompletedPayload", completed_view_selection_js)
        self.assertIn("completed-pending-proof-summary", html)
        self.assertIn("completed-pending-proof-detail", html)
        self.assertIn("function completedValidationChecklistLines", completed_view_review_js)
        self.assertIn("function completedRowReviewChecklistLines", completed_view_review_js)
        self.assertIn("function completedRowIssueDigestLines", completed_view_review_js)
        self.assertIn("function completedRowCombinedReviewPlanLines", completed_view_review_js)
        self.assertIn("function completedSelectedQuickSignalLines", completed_view_review_js)
        self.assertIn("function completedSelectedOpenTargetLines", completed_view_open_actions_js)
        self.assertIn("Open boundary: Completed buttons send only row_key and target.", completed_view_open_actions_js)
        self.assertIn("available_open_target_counts", completed_view_js)
        self.assertIn("function completedFilterVisibilityLines", completed_view_review_js)
        self.assertIn("function completedFocusedInvestigationLabels", completed_view_review_js)
        self.assertIn("function resetCompletedFilters", completed_view_filters_js)
        self.assertIn("Current Output Status filters cleared.", completed_view_filters_js)
        self.assertIn("function resetCompletedHistoryFilters", completed_view_filters_js)
        self.assertIn("completed-clear-filters-button", html)
        self.assertIn("completedClearFiltersButton.addEventListener(\"click\", resetCompletedFilters)", js)
        self.assertIn("function completedInvestigationSignalLines", completed_view_review_js)
        self.assertIn("function createCompletedDiagnosticsModule", completed_view_diagnostics_js)
        self.assertIn("window.__completedViewDiagnosticsModule", completed_view_diagnostics_js)
        self.assertIn("const completedDiagnosticsModule = window.__completedViewDiagnosticsModule || {}", completed_view_js)
        self.assertIn("delete window.__completedViewDiagnosticsModule", completed_view_js)
        self.assertIn("function completedDiagnosticsActionsForRow", completed_view_diagnostics_js)
        self.assertIn("function renderCompletedDiagnosticsLinks", completed_view_diagnostics_js)
        self.assertIn("async function requestCompletedDiagnosticsAction", completed_view_diagnostics_js)
        self.assertNotIn("function completedDiagnosticsActionsForRow", completed_view_js)
        self.assertNotIn("function renderCompletedDiagnosticsLinks", completed_view_js)
        self.assertNotIn("function requestCompletedDiagnosticsAction", completed_view_js)
        self.assertIn("Manifest Check", html)
        self.assertIn("Output Checklist", html)
        self.assertIn("Consistency statuses:", completed_view_review_js)
        self.assertIn("Missing sidecars:", completed_view_review_js)
        self.assertIn("Output/sidecar mismatches:", completed_view_review_js)
        self.assertIn("Mutation guardrail: this panel is read-only.", completed_view_review_js)
        self.assertIn("function completedFreshnessLine", completed_view_status_boards_js)
        self.assertIn("function completedManifestIsAged", completed_view_status_boards_js)
        self.assertIn("Manifest age", completed_view_review_js)
        self.assertIn("History aged", completed_view_review_js)
        self.assertIn("Operator status:", completed_view_selection_js)
        self.assertIn("Operator statuses:", completed_view_js)
        self.assertIn("Operator severities:", completed_view_js)
        self.assertIn("Backend trust states:", completed_view_js)
        self.assertIn("Backend trust state:", completed_view_selection_js)
        self.assertIn("Backend proof summary:", completed_view_selection_js)
        self.assertIn("operator_trust_state", completed_view_selection_js)
        self.assertIn("safe_next_action", completed_view_selection_js)
        self.assertIn("unsafe_if_ignored", completed_view_selection_js)
        self.assertIn("recommended_diagnostics_targets", completed_view_selection_js)
        self.assertIn("Review flags:", completed_view_selection_js)
        self.assertIn("Route decision:", completed_view_selection_js)
        self.assertIn("Route evidence:", completed_view_selection_js)
        self.assertIn("route_evidence_lines", completed_view_selection_js)
        self.assertIn("operator_guidance", completed_view_selection_js)
        self.assertIn("Rows needing review:", completed_view_js)
        self.assertIn("Rows over +5% output growth:", completed_view_js)
        self.assertIn("Real-media validation checklist:", completed_view_review_js)
        self.assertIn("desktop_validation_state.v1", completed_view_review_js)
        self.assertIn("Proof boundary: this checklist does not run ffprobe, hash files, or mark playback accepted.", completed_view_review_js)
        self.assertIn("Validation state:", completed_view_selection_js)
        self.assertIn("Validation state proof", completed_view_proof_js)
        self.assertIn("Selected completed-row review checklist:", completed_view_review_js)
        self.assertIn("Selected completed-row quick signal:", completed_view_review_js)
        self.assertIn("Current filter visibility:", completed_view_review_js)
        self.assertIn("Hidden by current filters:", completed_view_review_js)
        self.assertIn("Selected completed issue digest:", completed_view_review_js)
        self.assertIn("Combined completed-row review plan:", completed_view_review_js)
        self.assertIn("Completed Manifest", completed_view_review_js)
        self.assertIn("Route/size proof", completed_view_review_js)
        self.assertIn("Guardrail: this combined plan is read-only and cannot repair manifests", completed_view_review_js)
        self.assertIn("Investigation view matches:", completed_view_review_js)
        self.assertIn("investigation views are display filters only and do not repair manifests", completed_view_review_js)
        self.assertIn("function completedRealMediaTraceLines", completed_view_review_js)
        self.assertIn("Real-media sample trace: Completed", completed_view_review_js)
        self.assertIn("What remains unproven: final publish success when output is parked", completed_view_review_js)
        self.assertIn("Safe next action: inspect Completed Manifest, Pending Publish, output folder, Run Logs, and Last Stderr before rerun.", completed_view_review_js)
        self.assertIn("Safe next action: compare route metadata and logs before accepting this output as intentional compatibility growth.", completed_view_review_js)
        self.assertIn("Mutation guardrail: selected-row detail is read-only", completed_view_review_js)
        self.assertIn("Diagnostics actions below use backend allowlists. The Completed page never sends arbitrary filesystem paths.", completed_view_diagnostics_js)
        self.assertIn("completed-diagnostics-actions", completed_view_diagnostics_js)
        self.assertIn("requestDiagnosticsOpen(target)", completed_view_diagnostics_js)
        self.assertIn("requestDiagnosticsTail(target)", completed_view_diagnostics_js)
        self.assertIn("Output growth:", completed_view_selection_js)
        self.assertIn("Mutation guardrail: repair, reconcile, and rerun actions must remain backend-owned commands.", completed_view_review_js)
        self.assertIn("function requestCompletedOpen", completed_view_open_actions_js)
        self.assertIn("/api/completed/open", completed_view_open_actions_js)
        self.assertIn("[data-open-completed]", completed_view_open_actions_js)
        self.assertIn("let completedOpenInFlight = false", completed_view_open_actions_js)
        self.assertIn("function setCompletedOpenBusy", completed_view_open_actions_js)
        self.assertIn("function rejectCompletedOpenWhileBusy", completed_view_open_actions_js)
        self.assertIn("function renderCompletedOpenHistory", completed_view_open_actions_js)
        self.assertIn("function isCompletedOpenCommand", completed_view_open_actions_js)
        self.assertIn("Backend manifest row keys and target allowlists remain the source of truth.", completed_view_open_actions_js)
        self.assertIn("function completedEmptyStateMessage", completed_view_status_boards_js)
        self.assertIn("No completed history rows.", completed_view_status_boards_js)
        self.assertIn("Select a completed row to see output, sidecar, size-growth", completed_view_review_js)
        self.assertIn("function completedRowTrustSummaryLines", completed_view_review_js)
        self.assertIn("review-before-rerun-or-cleanup", completed_view_review_js)
        self.assertIn("delete outputs, rerun sources, repair manifests", completed_view_review_js)
        self.assertIn("appendDiagnosticsBridgeGroupedButtons(container, actions", completed_view_diagnostics_js)
        self.assertIn("Audio/subtitle decisions:", completed_view_review_js)
        self.assertIn("audio_decision_preview", completed_view_selection_js)
        self.assertIn("subtitle_decision_preview", completed_view_selection_js)
        self.assertIn("Rows with exact source/output runtime history:", completed_view_review_js)
        self.assertIn("Runtime outcome matches:", completed_view_review_js)
        self.assertIn("Stale history is shown only as context.", completed_view_review_js)
        self.assertIn("Runtime error code:", completed_view_selection_js)
        self.assertIn("Runtime match:", completed_view_selection_js)
        self.assertIn("Route reason:", completed_view_selection_js)
        self.assertIn("Another completed open command is already in progress.", completed_view_open_actions_js)
        self.assertIn("button.disabled = completedOpenInFlight", completed_view_open_actions_js)
        self.assertIn("window.mediaPipelineQueueView", queue_view_js)
        self.assertIn("function renderQueue", queue_view_js)
        self.assertIn("function renderQueueRows", queue_view_js)
        self.assertIn("function selectQueueRow", queue_view_js)
        self.assertIn("function renderQueueProgress", queue_view_js)
        self.assertIn("function queueProgressBars", queue_view_js)
        self.assertIn("const progressRenderer = window.mediaPipelineProgressView?.renderProgressBarsInto", queue_view_js)
        self.assertIn("progressRenderer(\"queue-progress-bars\"", queue_view_js)
        self.assertIn("queue-progress-bars", html)
        self.assertIn("queue-progress-summary", html)
        self.assertIn("function renderQueueCollision", queue_view_js)
        self.assertIn("function queueCollisionStatus", queue_view_js)
        self.assertIn("function queueCollisionLines", queue_view_js)
        self.assertIn("function renderQueueExcluded", queue_view_js)
        self.assertIn("function renderQueueExcludedDetail", queue_view_js)
        self.assertIn("function selectQueueExcludedRow", queue_view_js)
        self.assertIn("function queueExcludedRowKey", queue_view_js)
        self.assertIn("row_scope", queue_view_js)
        self.assertIn("Collision Risk", html)
        self.assertIn("Queue Decision", html)
        self.assertIn("queue-decision-summary", html)
        self.assertIn("Attention Required", html)
        self.assertIn("queue-attention-summary", html)
        self.assertIn("Search loaded queue rows", html)
        self.assertIn("Display status filter", html)
        self.assertIn("Investigation view", html)
        self.assertIn("Clear Display Filters", html)
        self.assertIn("Selected Row Detail (not launch scope)", html)
        self.assertIn("Backend Launch Scope Boundary", html)
        self.assertIn("Queue-to-Launch Handoff", html)
        self.assertIn("Backend-Excluded Source Files", html)
        self.assertIn("Selected Row Diagnostics Links", html)
        queue_panel_order = [
            "<h2>Queue Decision</h2>",
            "<h2>Source Scan And Display Filters</h2>",
            "<h2>Attention Required</h2>",
            "<h2>Queue Rows</h2>",
            "<h2>Selected Row Detail (not launch scope)</h2>",
            "<h2>Selected Row Diagnostics Links</h2>",
            "<h2>Backend Launch Scope Boundary</h2>",
            "<h2>Queue-to-Launch Handoff</h2>",
            "<h2>Source Scan Progress</h2>",
            "<h2>Queue Snapshot</h2>",
            "<h2>Readiness</h2>",
            "<h2>Queue Summary</h2>",
            "<h2>Run History</h2>",
            "<h2>Queue Readiness Checklist</h2>",
            "<h2>Next Step</h2>",
            "<h2>Flagged Items</h2>",
            "<h2>Collision Risk</h2>",
            "<h2>Backend-Excluded Source Files</h2>",
        ]
        queue_page_html = html[html.index('data-page-panel="queue"') :]
        queue_panel_positions = [queue_page_html.index(marker) for marker in queue_panel_order]
        self.assertEqual(queue_panel_positions, sorted(queue_panel_positions))
        self.assertIn("Row-level excluded-file detail: unavailable", queue_view_js)
        self.assertIn("function renderQueueDetail", queue_view_js)
        self.assertIn("function renderQueueSummary", queue_view_js)
        self.assertIn("function renderQueueReadiness", queue_view_js)
        self.assertIn("function renderQueueBreakdown", queue_view_js)
        self.assertIn("function renderQueueRuntime", queue_view_js)
        self.assertIn("function renderQueueValidation", queue_view_js)
        self.assertIn("function renderQueueBackendLaunchScopePreview", queue_view_js)
        self.assertIn("function queueBackendLaunchScopeRows", queue_view_js)
        self.assertIn("function renderQueueDecisionHeader", queue_view_js)
        self.assertIn("function renderQueueAttentionSummary", queue_view_js)
        self.assertIn("Queue decision header:", queue_view_js)
        self.assertIn("Attention required:", queue_view_js)
        self.assertIn("Backend launch scope boundary:", queue_view_js)
        self.assertIn("Queue filters, row selection, and rendered table caps are not submitted as processing scope.", queue_view_js)
        self.assertIn("Backend launch scope is owned by Launch; Queue filters, selected rows, and rendered row caps are not submitted as processing scope.", queue_view_js)
        self.assertIn("Selecting a row cannot make Launch process only that row.", queue_view_js)
        self.assertIn("function renderQueueLaunchDecisionChecklist", queue_view_js)
        self.assertIn("function queueLaunchDecisionRows", queue_view_js)
        self.assertIn("function queueLaunchDecisionStatusState", queue_view_js)
        self.assertIn("function launchViewApi", queue_view_js)
        self.assertIn("function queueCurrentFilterScope", queue_view_js)
        self.assertIn("function queueFilterScopeDetailLines", queue_view_js)
        self.assertIn("Display filter / backend launch scope", queue_view_js)
        self.assertIn("Backend launch scope: unchanged.", queue_view_js)
        self.assertIn("Launch routes use backend queue/schedule/settings checks, not the visible WebView table subset.", queue_view_js)
        self.assertIn("renderQueueLaunchDecisionChecklist(lastQueuePayload, lastQueueRows", queue_view_js)
        self.assertIn("function queueLaunchBackendPreflightPayload", queue_view_js)
        self.assertIn("function queueLaunchBackendPreflightCheckpoint", queue_view_js)
        self.assertIn('launchView.launchBackendPreflightPayloadForTarget("pipeline")', queue_view_js)
        self.assertIn("launchView.getLastLaunchBackendPreflightRefreshInfo()", queue_view_js)
        self.assertIn("Last backend preflight refresh:", queue_view_js)
        self.assertIn("Backend launch preflight", queue_view_js)
        self.assertIn("Pipeline backend launch preflight has not been loaded", queue_view_js)
        self.assertIn("function isQueueLaunchCommand", queue_view_js)
        self.assertIn("Queue-to-Launch handoff:", queue_view_js)
        self.assertIn("Daily-use handoff: Queue evidence decides whether it is sensible to open Launch", queue_view_js)
        self.assertIn("Scope boundary: Queue filters, selected rows, review boards", queue_view_js)
        self.assertIn("open Launch only after backend launch preflight, queue payload, display filter scope, freshness, blocked rows, runtime context, completed exclusions, selected-row proof, command history, and Launch readiness agree.", queue_view_js)
        self.assertIn("Mutation guardrail: this handoff cannot launch, reorder, drop, rewrite queue snapshots, delete files, clear completed state, override schedule, or bypass backend validation.", queue_view_js)
        self.assertIn("queue-launch-decision-summary", html)
        self.assertIn("queue-launch-decision-detail", html)
        self.assertIn("function renderQueueReviewBoard", queue_view_js)
        self.assertIn("function queueReviewBoardLines", queue_view_js)
        self.assertIn("Operator review board: Queue", queue_view_js)
        self.assertIn("queue-review-board", html)
        self.assertIn("function queueValidationChecklistLines", queue_view_js)
        self.assertIn("function queueRowReviewChecklistLines", queue_view_js)
        self.assertIn("function queueRowIssueDigestLines", queue_view_js)
        self.assertIn("function queueRowCombinedReviewPlanLines", queue_view_js)
        self.assertIn("function queueSelectedQuickSignalLines", queue_view_js)
        self.assertIn("function queueSelectedOpenTargetLines", queue_view_js)
        self.assertIn("Open boundary: Queue buttons send only row_key, row_scope, and target.", queue_view_js)
        self.assertIn("available_open_target_counts", queue_view_js)
        self.assertIn("function queueFilterVisibilityLines", queue_view_js)
        self.assertIn("function queueFocusedInvestigationLabels", queue_view_js)
        self.assertIn("function resetQueueFilters", queue_view_js)
        self.assertIn("Queue display filters cleared.", queue_view_js)
        self.assertIn("queue-clear-filters-button", html)
        self.assertIn("data-queue-refresh-button", html)
        self.assertIn("Scan Sources asks the backend to inventory configured source roots", html)
        self.assertIn("queue-source-inventory", html)
        self.assertIn("[data-queue-refresh-button]", queue_view_js)
        self.assertIn("/api/queue/scan", queue_view_js)
        self.assertIn("function requestQueueScan()", queue_view_js)
        self.assertIn("window.mediaPipelineAppRefresh?.renderQueueRefreshInProgress?.();", queue_view_js)
        self.assertIn("function renderQueueRefreshInProgress()", app_refresh_js)
        self.assertIn('activity: "Scanning"', app_refresh_js)
        self.assertIn("setQueueRefreshButtonBusy(true)", app_refresh_js)
        self.assertIn("setQueueRefreshButtonBusy(queueScanRunning)", app_refresh_js)
        self.assertLess(html.index('data-queue-refresh-button'), html.index('id="queue-rows"'))
        self.assertLess(html.index('id="queue-rows"'), html.index('id="queue-readiness"'))
        self.assertIn("queueClearFiltersButton.addEventListener(\"click\", resetQueueFilters)", js)
        self.assertIn("function queueInvestigationSignalLines", queue_view_js)
        self.assertIn("function queueRowTrustSummaryLines", queue_view_js)
        self.assertIn("function queueDiagnosticsActionsForRow", queue_view_js)
        self.assertIn("function renderQueueDiagnosticsLinks", queue_view_js)
        self.assertIn("function requestQueueDiagnosticsAction", queue_view_js)
        self.assertIn("function requestQueueOpen", queue_view_js)
        self.assertIn("function renderQueueOpenHistory", queue_view_js)
        self.assertIn("function isQueueOpenCommand", queue_view_js)
        self.assertIn("function queueReadinessStatus", queue_view_js)
        self.assertIn("function queueReadinessLines", queue_view_js)
        self.assertIn("function queueBreakdownLines", queue_view_js)
        self.assertIn("function queueRuntimeLines", queue_view_js)
        self.assertIn("Run History", html)
        self.assertIn("function queueEmptyStateMessage", queue_view_js)
        self.assertIn("window.getLastQueuePayload = getLastQueuePayload", queue_view_js)
        self.assertIn("window.getLastQueueRows = getLastQueueRows", queue_view_js)
        self.assertIn("/api/queue/open", queue_view_js)
        self.assertIn("Another queue open command is already in progress.", queue_view_js)
        self.assertIn("Backend queue snapshot row keys and target allowlists remain the source of truth.", queue_view_js)
        self.assertIn("Mutation guardrail: backend queue mutation and processing start remain backend-owned commands", queue_view_js)
        self.assertIn("Route reasons:", queue_view_js)
        self.assertIn("Invalid snapshot rows:", queue_view_js)
        self.assertIn("Operator note: this is a read-only snapshot breakdown.", queue_view_js)
        self.assertIn("No runnable queue rows.", queue_view_js)
        self.assertIn("Select a queue row to see launch readiness", queue_view_js)
        self.assertIn("Source candidates:", queue_view_js)
        self.assertIn("Completed/blocked exclusions:", queue_view_js)
        self.assertIn("Visible blocked rows:", queue_view_js)
        self.assertIn("Visible blocked reason codes:", queue_view_js)
        self.assertIn("Visible blocked reasons:", queue_view_js)
        self.assertIn("Runtime checks deferred:", queue_view_js)
        self.assertIn("Runtime deferred checks:", queue_view_js)
        self.assertIn("Runtime outcome matches:", queue_view_js)
        self.assertIn("Rows with exact source-path runtime history:", queue_view_js)
        self.assertIn("Stale history is shown only as context.", queue_view_js)
        self.assertIn("Real-media validation checklist:", queue_view_js)
        self.assertIn("Mutation guardrail: this checklist", queue_view_js)
        self.assertIn("Selected row review checklist:", queue_view_js)
        self.assertIn("Selected row quick signal:", queue_view_js)
        self.assertIn("Current filter visibility:", queue_view_js)
        self.assertIn("Hidden by current filters:", queue_view_js)
        self.assertIn("Selected queue issue digest:", queue_view_js)
        self.assertIn("Combined row review plan:", queue_view_js)
        self.assertIn("Queue Snapshot", queue_view_js)
        self.assertIn("Launch readiness", queue_view_js)
        self.assertIn("Guardrail: this combined plan is read-only and cannot change queue order", queue_view_js)
        self.assertIn("Investigation view matches:", queue_view_js)
        self.assertIn("investigation views are display filters only and do not alter backend launch scope", queue_view_js)
        self.assertIn("function queueRealMediaTraceLines", queue_view_js)
        self.assertIn("Real-media sample trace: Queue", queue_view_js)
        self.assertIn("What remains unproven: FFmpeg execution", queue_view_js)
        self.assertIn("review-before-launch", queue_view_js)
        self.assertIn("diagnosticsBridgeRowTrustLines", queue_view_js)
        self.assertIn("appendDiagnosticsBridgeGroupedButtons(container, actions", queue_view_js)
        self.assertIn("Safe next action: use Queue Diagnostics Cross-Links before launch", queue_view_js)
        self.assertIn("Safe next action: row is coherent in the current snapshot", queue_view_js)
        self.assertIn("selected-row detail is read-only", queue_view_js)
        self.assertIn("Diagnostics actions below use backend allowlists. The Queue page never sends arbitrary filesystem paths.", queue_view_js)
        self.assertIn("queue-diagnostics-actions", queue_view_js)
        self.assertIn("requestDiagnosticsOpen(target)", queue_view_js)
        self.assertIn("requestDiagnosticsTail(target)", queue_view_js)
        self.assertIn("Runtime error code:", queue_view_js)
        self.assertIn("Runtime match:", queue_view_js)
        self.assertIn("Produced:", queue_view_js)
        self.assertIn("Snapshot file age", queue_view_js)
        self.assertIn("Produced age", queue_view_js)
        self.assertIn("Snapshot stale", queue_view_js)
        self.assertIn("function queueSnapshotIsStale", queue_view_js)
        self.assertIn("Operator status:", queue_view_js)
        self.assertIn("Blocked reason code:", queue_view_js)
        self.assertIn("Runtime note:", queue_view_js)
        self.assertIn("Operator statuses:", queue_view_js)
        self.assertIn("Operator severities:", queue_view_js)
        self.assertIn("Backend trust states:", queue_view_js)
        self.assertIn("Backend trust state:", queue_view_js)
        self.assertIn("Backend proof summary:", queue_view_js)
        self.assertIn("operator_trust_state", queue_view_js)
        self.assertIn("safe_next_action", queue_view_js)
        self.assertIn("unsafe_if_ignored", queue_view_js)
        self.assertIn("recommended_diagnostics_targets", queue_view_js)
        self.assertIn("Review flags:", queue_view_js)
        self.assertIn("Route decision:", queue_view_js)
        self.assertIn("Route evidence:", queue_view_js)
        self.assertIn("route_evidence_lines", queue_view_js)
        self.assertIn("operator_guidance", queue_view_js)
        self.assertIn("Source roots:", queue_view_js)
        self.assertIn("window.mediaPipelineCrossPageContextView", cross_page_context_view_js)
        self.assertIn("function renderCrossPageContext", cross_page_context_view_js)
        self.assertIn("function crossPageContextLines", cross_page_context_view_js)
        self.assertIn("function crossPageInvestigationOrder", cross_page_context_view_js)
        self.assertIn("window.__crossPageConflictModule", cross_page_conflict_js)
        self.assertIn("const __conflictMod = window.__crossPageConflictModule || {}", cross_page_context_view_js)
        self.assertIn("delete window.__crossPageConflictModule", cross_page_context_view_js)
        self.assertIn("function renderCrossPageConflictBoard", cross_page_conflict_js)
        self.assertIn("function crossPageConflictRows", cross_page_conflict_js)
        self.assertIn("function crossPageConflictSummary", cross_page_conflict_js)
        self.assertIn("window.__crossPageSampleModule", cross_page_sample_js)
        self.assertIn("const __sampleMod = window.__crossPageSampleModule || {}", cross_page_context_view_js)
        self.assertIn("delete window.__crossPageSampleModule", cross_page_context_view_js)
        self.assertIn("function renderCrossPageSampleCorrelation", cross_page_sample_js)
        self.assertIn("function crossPageSampleRows", cross_page_sample_js)
        self.assertIn("function crossPageSampleEvidenceForSeed", cross_page_sample_js)
        self.assertIn("function crossPageValidationTemplateLines", cross_page_sample_js)
        self.assertIn("function renderCrossPageValidationTemplate", cross_page_sample_js)
        self.assertIn("window.__crossPageSettingsModule", cross_page_settings_js)
        self.assertIn("const __settingsMod = window.__crossPageSettingsModule || {}", cross_page_context_view_js)
        self.assertIn("delete window.__crossPageSettingsModule", cross_page_context_view_js)
        self.assertIn("function crossPageSettingsPolicyEvidence", cross_page_settings_js)
        self.assertIn("function crossPageSampleValidationEvidence", cross_page_sample_validation_js)
        self.assertIn("function crossPageRealMediaWorksheetRows", cross_page_sample_validation_js)
        self.assertIn("function crossPageRealMediaWorksheetStatus", cross_page_sample_validation_js)
        self.assertIn("function renderCrossPageRealMediaWorksheet", cross_page_sample_validation_js)
        self.assertIn("Filename-only match; compare folders before trusting it.", cross_page_sample_js)
        self.assertIn("Completed output/sidecar proof is not exact-matched yet.", cross_page_sample_js)
        self.assertIn("No cross-page evidence for this sample is visible in loaded payloads.", cross_page_sample_js)
        self.assertIn("Real-media validation log template:", cross_page_sample_js)
        self.assertIn("Real-media validation worksheet:", cross_page_sample_validation_js)
        self.assertIn("Queue route intent, Completed output proof, Pending Publish final-destination proof", cross_page_sample_validation_js)
        self.assertIn("Sample Validation evidence posture", cross_page_sample_validation_js)
        self.assertIn("Sample Validation readiness", cross_page_sample_validation_js)
        self.assertIn("Sample Validation is evidence-only", cross_page_sample_validation_js)
        self.assertIn("Sample validation:", cross_page_sample_validation_js)
        self.assertIn("Saved media policy", cross_page_sample_validation_js)
        self.assertIn("This worksheet is read-only", cross_page_sample_validation_js)
        self.assertIn("Boundary: this worksheet does not save, accept, repair, rerun, drain, delete, publish, rename, rewrite manifests, or touch media files.", cross_page_sample_validation_js)
        self.assertIn("Generated from loaded WebView payloads only.", cross_page_sample_js)
        self.assertIn("use the backend-owned Sample Validation Record panel below", cross_page_sample_js)
        self.assertIn("function sampleValidationCheckedSummary", cross_page_sample_validation_js)
        self.assertIn("SAMPLE_VALIDATION_CHECK_FIELDS", cross_page_sample_validation_js)
        self.assertIn("function sampleValidationMergedChecks", cross_page_sample_validation_js)
        self.assertIn("function sampleValidationShellSurface", cross_page_sample_validation_js)
        self.assertIn('shell: sampleValidationShellSurface()', cross_page_sample_validation_js)
        self.assertIn("function sampleValidationRecordComparisonRowsForPaths", cross_page_sample_validation_js)
        self.assertIn("function syncSampleValidationCheckControls", cross_page_sample_validation_js)
        self.assertIn("Manual sample-validation checks cleared", cross_page_sample_validation_js)
        self.assertIn("function sampleValidationLogSummaryLines", cross_page_sample_validation_js)
        self.assertIn("function sampleValidationAuditSummaryLines", cross_page_sample_validation_js)
        self.assertIn("Real-media validation audit:", cross_page_sample_validation_js)
        self.assertIn("Boundary: validation audit is read-only", cross_page_sample_validation_js)
        self.assertIn("function sampleValidationPolicyAlignmentSummaryLines", cross_page_sample_validation_js)
        self.assertIn("Real-media policy alignment:", cross_page_sample_validation_js)
        self.assertIn("Read-only real-media policy alignment", cross_page_sample_validation_js)
        self.assertIn("function launchPolicyAlignmentQueueIntentEvidence", launch_view_realmedia_js)
        self.assertIn("Saved policy vs Queue route:", launch_view_realmedia_js)
        self.assertIn("Saved policy vs Queue route evidence packet:", launch_view_realmedia_js)
        self.assertIn("Advisory boundary: queue-route matching uses loaded route/status text only.", launch_view_realmedia_js)
        self.assertIn("function sampleValidationReadinessLines", cross_page_sample_validation_js)
        self.assertIn("function sampleValidationReconciliationLines", cross_page_sample_validation_js)
        self.assertIn("function sampleValidationGapSummaryLines", cross_page_sample_validation_js)
        self.assertIn("function renderSampleValidationGapSummary", cross_page_sample_validation_js)
        self.assertIn("Real-media evidence gap summary:", cross_page_sample_validation_js)
        self.assertIn("Read-only real-media evidence-gap summary", cross_page_sample_validation_js)
        self.assertIn("function sampleValidationRunbookSummaryLines", cross_page_sample_validation_js)
        self.assertIn("function renderSampleValidationRunbook", cross_page_sample_validation_js)
        self.assertIn("Real-media pilot runbook:", cross_page_sample_validation_js)
        self.assertIn("# Real-Media WebView Pilot Runbook", cross_page_sample_validation_js)
        self.assertIn("Read-only real-media pilot runbook", cross_page_sample_validation_js)
        self.assertIn("function sampleValidationExecutionRows", cross_page_sample_validation_js)
        self.assertIn("function renderSampleValidationExecutionChecklist", cross_page_sample_validation_js)
        self.assertIn("Operator-selected real-media sample execution:", cross_page_sample_validation_js)
        self.assertIn("Proposed evidence coverage:", cross_page_sample_validation_js)
        self.assertIn("Backend readiness:", cross_page_sample_validation_js)
        self.assertIn("Readiness next action:", cross_page_sample_validation_js)
        self.assertIn("Current evidence reconciliation:", cross_page_sample_validation_js)
        self.assertIn("Append readiness:", cross_page_sample_validation_js)
        self.assertIn("Post-run evidence capture:", cross_page_sample_validation_js)
        self.assertIn("Copyable post-run Markdown:", cross_page_sample_validation_js)
        self.assertIn("function sampleValidationCompletedPacketRows", cross_page_sample_validation_js)
        self.assertIn("function sampleValidationCompletedPolicyReconciliationRow", cross_page_sample_validation_js)
        self.assertIn("function sampleValidationCompletedPolicyReconciliationStatus", cross_page_sample_validation_js)
        self.assertIn("function renderSampleValidationCompletedPacketHandoff", cross_page_sample_validation_js)
        self.assertIn("Completed evidence handoff for Sample Validation:", cross_page_sample_validation_js)
        self.assertIn("Saved-policy reconciliation:", cross_page_sample_validation_js)
        self.assertIn("window.sampleValidationCompletedPolicyReconciliationRow = sampleValidationCompletedPolicyReconciliationRow", cross_page_context_view_js)
        self.assertIn("Decision rule: keep Sample Validation at hold/review", cross_page_sample_validation_js)
        _assert_namespace_export(self, cross_page_context_view_js, "mediaPipelineCrossPageContextView", "renderSampleValidationCompletedPacketHandoff")
        self.assertIn("function sampleValidationAcceptanceGateRows", cross_page_sample_validation_js)
        self.assertIn("function renderSampleValidationAcceptanceGate", cross_page_sample_validation_js)
        self.assertIn("Sample Validation acceptance readiness gate:", cross_page_sample_validation_js)
        self.assertIn("Saved policy reconciliation", cross_page_sample_validation_js)
        self.assertIn("Missing visible category tokens are review gaps", cross_page_sample_validation_js)
        self.assertIn("Decision rule: accepted sample evidence should not be appended", cross_page_sample_validation_js)
        _assert_namespace_export(self, cross_page_context_view_js, "mediaPipelineCrossPageContextView", "renderSampleValidationAcceptanceGate")
        self.assertIn("function sampleValidationRecordReviewRows", cross_page_sample_validation_js)
        self.assertIn("function renderSampleValidationRecordReview", cross_page_sample_validation_js)
        self.assertIn("Accepted sample-validation record proof review:", cross_page_sample_validation_js)
        self.assertIn("Decision rule: treat accepted records as current proof only", cross_page_sample_validation_js)
        _assert_namespace_export(self, cross_page_context_view_js, "mediaPipelineCrossPageContextView", "renderSampleValidationRecordReview")
        self.assertIn("function sampleValidationCategorySummaryRows", cross_page_sample_validation_js)
        self.assertIn("function renderSampleValidationCategorySummary", cross_page_sample_validation_js)
        self.assertIn("Pilot category validation summary:", cross_page_sample_validation_js)
        self.assertIn("Decision rule: a category is ready only when an accepted validation record", cross_page_sample_validation_js)
        _assert_namespace_export(self, cross_page_context_view_js, "mediaPipelineCrossPageContextView", "renderSampleValidationCategorySummary")
        self.assertIn("Read-only post-run evidence capture packet", cross_page_sample_validation_js)
        self.assertIn("Required acceptance gaps:", cross_page_sample_validation_js)
        self.assertIn("Recommended review gaps:", cross_page_sample_validation_js)
        self.assertIn("Read-only append-readiness advice", cross_page_sample_validation_js)
        self.assertIn("Reconciliation is read-only", cross_page_sample_validation_js)
        self.assertIn("Sample validation records are notes/evidence only", cross_page_sample_validation_js)
        self.assertIn("Queue route/remux-vs-encode reason checked", cross_page_sample_js)
        self.assertIn("this template does not save, accept, repair, rerun, drain, delete, publish, rewrite manifests, or touch media files", cross_page_sample_js)
        self.assertIn("Operator investigation order:", cross_page_context_view_js)
        self.assertIn("Diagnostics: resolve refresh failures", cross_page_context_view_js)
        self.assertIn("Pending Publish: review do-not-drain", cross_page_context_view_js)
        self.assertIn("Launch: start backend-owned processing", cross_page_context_view_js)
        self.assertIn("Exact-match cross-checks:", cross_page_context_view_js)
        self.assertIn("Queued source also in Completed source history:", cross_page_context_view_js)
        self.assertIn("Pending destination also in Completed output history:", cross_page_context_view_js)
        self.assertIn("Cross-page conflict board:", cross_page_conflict_js)
        self.assertIn("same-leaf rows are duplicate-title hints only", cross_page_conflict_js)
        self.assertIn("Completed has missing-output rows while Pending Publish is empty.", cross_page_context_view_js)
        self.assertIn("Missing-output posture: Completed reports missing outputs while Pending Publish is empty", cross_page_context_view_js)
        self.assertIn("queued-source-pending-publish", cross_page_conflict_js)
        self.assertIn("Mutation guardrail: this panel does not start, repair, rerun, drain, delete, or rewrite files.", cross_page_context_view_js)
        self.assertIn("window.mediaPipelinePendingPublishView", pending_publish_view_js)
        self.assertIn("function renderPendingPublish", pending_publish_view_js)
        self.assertIn("function renderPendingRows", pending_publish_view_js)
        self.assertIn("function selectPendingRow", pending_publish_view_js)
        self.assertIn("function renderPendingDetail", pending_publish_view_js)
        self.assertIn("function renderPendingPublishReadiness", pending_publish_view_js)
        self.assertIn("function renderPendingRiskBreakdown", pending_publish_view_js)
        self.assertIn("function renderPendingValidation", pending_publish_view_js)
        self.assertIn("function renderPendingReviewBoard", pending_publish_view_js)
        self.assertIn("function pendingReviewBoardLines", pending_publish_view_js)
        self.assertIn("Operator review board: Pending Publish", pending_publish_view_js)
        self.assertIn("pending-review-board", html)
        self.assertIn("function renderPendingDrainEvidence", pending_publish_drain_js)
        self.assertIn("function pendingEvidenceRows", pending_publish_drain_js)
        self.assertIn("function pendingDrainEvidenceLines", pending_publish_drain_js)
        self.assertIn("Pending drain evidence board:", pending_publish_drain_js)
        self.assertIn("No pending rows with drain blockers or review evidence.", pending_publish_drain_js)
        self.assertIn("function renderPendingDrainEvents", pending_publish_drain_js)
        self.assertIn("function renderPendingDrainSummary", pending_publish_drain_js)
        self.assertIn("function pendingPublishReadinessStatus", pending_publish_view_js)
        self.assertIn("function pendingPublishReadinessLines", pending_publish_view_js)
        self.assertIn("function pendingRiskLines", pending_publish_view_js)
        self.assertIn("function pendingValidationChecklistLines", pending_publish_view_js)
        self.assertIn("function pendingRowReviewChecklistLines", pending_publish_view_js)
        self.assertIn("function pendingRowIssueDigestLines", pending_publish_view_js)
        self.assertIn("function pendingRowCombinedReviewPlanLines", pending_publish_view_js)
        self.assertIn("function pendingSelectedQuickSignalLines", pending_publish_view_js)
        self.assertIn("function pendingSelectedOpenTargetLines", pending_publish_diagnostics_js)
        self.assertIn("Open boundary: Pending Publish buttons send only row_key and target.", pending_publish_diagnostics_js)
        self.assertIn("available_open_target_counts", pending_publish_view_js)
        self.assertIn("function pendingFilterVisibilityLines", pending_publish_view_js)
        self.assertIn("function pendingFocusedInvestigationLabels", pending_publish_view_js)
        self.assertIn("function resetPendingFilters", pending_publish_view_js)
        self.assertIn("Pending Publish display filters cleared.", pending_publish_view_js)
        self.assertIn("pending-clear-filters-button", html)
        self.assertIn("pendingClearFiltersButton.addEventListener(\"click\", () => window.mediaPipelinePendingPublishView?.resetPendingFilters?.())", js)
        self.assertIn("function pendingInvestigationSignalLines", pending_publish_view_js)
        self.assertIn("function pendingRealMediaTraceLines", pending_publish_view_js)
        self.assertIn("function pendingSelectedCompletedCorrelationRows", pending_publish_view_js)
        self.assertIn("function pendingSelectedCompletedCorrelationLines", pending_publish_view_js)
        self.assertIn("function pendingSampleValidationHandoffLines", pending_publish_view_js)
        self.assertIn("Sample Validation handoff: Pending Publish", pending_publish_view_js)
        self.assertIn("function pendingSampleValidationComparisonLines", pending_publish_view_js)
        self.assertIn("Sample Validation comparison for selected Pending Publish row:", pending_publish_view_js)
        self.assertIn("Post-run capture: Preview Record includes pending/final-placement proof rows", pending_publish_view_js)
        self.assertIn("Suggested pilot category: deferred-publish", pending_publish_view_js)
        self.assertIn("Home Sample Validation can write JSONL evidence notes only", pending_publish_view_js)
        self.assertIn("Completed Manifest correlation for selected pending row:", pending_publish_view_js)
        self.assertIn("Exact pending destination -> completed output:", pending_publish_view_js)
        self.assertIn("Boundary: same-leaf matches are duplicate-title hints only", pending_publish_view_js)
        self.assertIn("Mutation guardrail: this pending-row correlation", pending_publish_view_js)
        self.assertIn("function pendingRowTrustSummaryLines", pending_publish_view_js)
        self.assertIn("Diagnostic statuses:", pending_publish_view_js)
        self.assertIn("Suggested open targets:", pending_publish_view_js)
        self.assertIn("Real-media validation checklist:", pending_publish_view_js)
        self.assertIn("Real-media sample trace: Pending Publish", pending_publish_view_js)
        self.assertIn("What remains unproven: final publish completion until Drain Parked Outputs succeeds", pending_publish_view_js)
        self.assertIn("Mutation guardrail: this checklist", pending_publish_view_js)
        self.assertIn("Selected pending-row review checklist:", pending_publish_view_js)
        self.assertIn("Selected pending-row quick signal:", pending_publish_view_js)
        self.assertIn("Current filter visibility:", pending_publish_view_js)
        self.assertIn("Hidden by current filters:", pending_publish_view_js)
        self.assertIn("Selected pending issue digest:", pending_publish_view_js)
        self.assertIn("Combined pending-row drain review plan:", pending_publish_view_js)
        self.assertIn("Pending manifest", pending_publish_view_js)
        self.assertIn("Completed Manifest correlation", pending_publish_view_js)
        self.assertIn("Guardrail: this combined plan is read-only and cannot drain", pending_publish_view_js)
        self.assertIn("Investigation view matches:", pending_publish_view_js)
        self.assertIn("investigation views are display filters only and do not change backend drain scope", pending_publish_view_js)
        self.assertIn("review-before-drain", pending_publish_view_js)
        self.assertIn("move, delete, drain, repair, or rewrite pending payloads", pending_publish_view_js)
        self.assertIn("appendDiagnosticsBridgeGroupedButtons(container, actions", pending_publish_diagnostics_js)
        self.assertIn("Safe next action: do not drain; inspect row targets, Pending Publish diagnostics, Last Stderr, and Run Logs first.", pending_publish_view_js)
        self.assertIn("Safe next action: row looks ready, but use only the backend-owned Drain Parked Outputs command to move files.", pending_publish_view_js)
        self.assertIn("Health blockers:", pending_publish_view_js)
        self.assertIn("Drain recommendation:", pending_publish_view_js)
        self.assertIn("Operator guidance:", pending_publish_view_js)
        self.assertIn("Backend trust states:", pending_publish_view_js)
        self.assertIn("Backend trust state:", pending_publish_view_js)
        self.assertIn("Backend proof summary:", pending_publish_view_js)
        self.assertIn("operator_trust_state", pending_publish_view_js)
        self.assertIn("safe_next_action", pending_publish_view_js)
        self.assertIn("unsafe_if_ignored", pending_publish_view_js)
        self.assertIn("recommended_diagnostics_targets", pending_publish_view_js)
        self.assertIn("function pendingListText", pending_publish_view_js)
        self.assertIn("function pendingDrainEventsFromSnapshot", pending_publish_drain_js)
        self.assertIn("function pendingDrainEventsLines", pending_publish_drain_js)
        self.assertIn("function pendingDrainSummaryLines", pending_publish_drain_js)
        self.assertIn("function pendingDrainSummaryPayload", pending_publish_drain_js)
        self.assertIn("function pendingRecoverySummaryPayload", pending_publish_view_js)
        self.assertIn("function pendingRecoverySummaryLines", pending_publish_view_js)
        self.assertIn("Backend recovery summary:", pending_publish_view_js)
        self.assertIn("Recovery classes:", pending_publish_view_js)
        self.assertIn("Recovery class:", pending_publish_view_js)
        self.assertIn("Recovery action:", pending_publish_view_js)
        self.assertIn("Evidence fields:", pending_publish_view_js)
        self.assertIn("function createPendingPublishDiagnosticsModule", pending_publish_diagnostics_js)
        self.assertIn("window.__pendingPublishDiagnosticsModule", pending_publish_diagnostics_js)
        self.assertIn("function pendingDiagnosticsActionsForRow", pending_publish_diagnostics_js)
        self.assertIn("function pendingDiagnosticsGuidanceLines", pending_publish_diagnostics_js)
        self.assertIn("function renderPendingDiagnosticsLinks", pending_publish_diagnostics_js)
        self.assertIn("function requestPendingDiagnosticsAction", pending_publish_diagnostics_js)
        self.assertIn("Diagnostics actions below use backend allowlists.", pending_publish_diagnostics_js)
        self.assertIn("button.dataset.pendingDiagnosticsAction", pending_publish_diagnostics_js)
        self.assertIn("openRequester(target)", pending_publish_diagnostics_js)
        self.assertIn("tailRequester(target)", pending_publish_diagnostics_js)
        self.assertIn("Selected-row diagnostic order:", pending_publish_diagnostics_js)
        self.assertIn("const pendingDiagnosticsModule = window.__pendingPublishDiagnosticsModule || {}", pending_publish_view_js)
        self.assertIn("delete window.__pendingPublishDiagnosticsModule", pending_publish_view_js)
        self.assertIn("pendingDiagnosticsModule.createPendingPublishDiagnosticsModule", pending_publish_view_js)
        self.assertIn("function createPendingPublishDrainModule", pending_publish_drain_js)
        self.assertIn("window.__pendingPublishDrainModule", pending_publish_drain_js)
        self.assertIn("const pendingDrainModule = window.__pendingPublishDrainModule || {}", pending_publish_view_js)
        self.assertIn("delete window.__pendingPublishDrainModule", pending_publish_view_js)
        self.assertIn("pendingDrainModule.createPendingPublishDrainModule", pending_publish_view_js)
        self.assertIn("function createPendingPublishConfidenceModule", pending_publish_confidence_js)
        self.assertIn("window.__pendingPublishConfidenceModule", pending_publish_confidence_js)
        self.assertIn("const pendingConfidenceModule = window.__pendingPublishConfidenceModule || {}", pending_publish_view_js)
        self.assertIn("delete window.__pendingPublishConfidenceModule", pending_publish_view_js)
        self.assertIn("pendingConfidenceModule.createPendingPublishConfidenceModule", pending_publish_view_js)
        self.assertIn("pending_drain_summary.v1", pending_publish_drain_js)
        self.assertIn("durable summary records the last backend drain attempt", pending_publish_drain_js)
        self.assertIn("publish_drained", pending_publish_drain_js)
        self.assertIn("Latest backend-authored drain events:", pending_publish_drain_js)
        self.assertIn("function renderPendingDrainHistory", pending_publish_drain_js)
        self.assertIn("function isPendingDrainCommand", pending_publish_drain_js)
        self.assertIn("function pendingDrainSearchText", pending_publish_drain_js)
        self.assertIn("function pendingEmptyStateMessage", pending_publish_view_js)
        self.assertIn("Ready-looking", pending_publish_view_js)  # readiness status chip (advisory, not a clearance)
        self.assertIn("Ready to drain:", pending_publish_view_js)  # data display label from backend ready_to_drain field
        self.assertIn("Issue summary:", pending_publish_view_js)
        self.assertIn("Operator note: drain readiness is advisory.", pending_publish_view_js)
        self.assertIn("Backend drain command remains the source of truth", pending_publish_view_js)
        self.assertIn("No parked outputs are waiting to publish.", pending_publish_view_js)
        self.assertIn("No pending publish drain commands found in command history.", pending_publish_drain_js)
        self.assertIn("Select a pending publish row to see drain safety", pending_publish_view_js)
        self.assertIn("function renderPendingDrainCorrelation", pending_publish_drain_js)
        self.assertIn("function pendingDrainCorrelationLines", pending_publish_drain_js)
        self.assertIn("Pending Publish drain correlation:", pending_publish_drain_js)
        self.assertIn("Mutation guardrail: this correlation is read-only", pending_publish_drain_js)
        self.assertIn("function pendingDrainConfidenceRows", pending_publish_confidence_js)
        self.assertIn("function renderPendingDrainActionConfidence", pending_publish_confidence_js)
        self.assertIn("entry.evidenceClass", pending_publish_confidence_js)
        self.assertIn("Pending Publish drain action confidence:", pending_publish_confidence_js)
        self.assertIn("This is the final read-only operator handoff before Drain Parked Outputs.", pending_publish_confidence_js)
        self.assertIn("Backend Drain Parked Outputs remains the only authority that can validate and move parked files.", pending_publish_confidence_js)
        self.assertIn("Build a selected-row or all-rows dry-run plan before risky drains.", pending_publish_confidence_js)
        self.assertIn("Mutation guardrail: this panel cannot drain, repair, rewrite, move, delete, publish, or bypass backend validation.", pending_publish_confidence_js)
        self.assertIn("function pendingCurrentFilterScope", pending_publish_drain_js)
        self.assertIn("Display filter / drain scope", pending_publish_confidence_js)
        self.assertIn("Backend drain scope remains all loaded parked rows", pending_publish_confidence_js)
        self.assertIn("Drain Parked Outputs does not drain only the visible table subset.", pending_publish_confidence_js)
        self.assertIn("pending-backend-scope-status", html)
        self.assertIn("pending-backend-scope-summary", html)
        self.assertIn("pending-backend-scope-rows", html)
        self.assertIn("function renderPendingBackendDrainScopePreview", pending_publish_drain_js)
        self.assertIn("function pendingBackendDrainScopeRows", pending_publish_drain_js)
        self.assertIn("Backend drain scope preview:", pending_publish_drain_js)
        self.assertIn("Pending filters, selected row keys, and rendered table caps are not submitted as publish scope.", pending_publish_drain_js)
        self.assertIn("Selecting a row cannot make Drain Parked Outputs drain only that row.", pending_publish_drain_js)
        self.assertIn("function renderPendingDrainDecisionChecklist", pending_publish_confidence_js)
        self.assertIn("function pendingDrainDecisionRows", pending_publish_confidence_js)
        self.assertIn("function pendingDrainDecisionStatusState", pending_publish_confidence_js)
        self.assertIn("Pending Publish drain decision checklist:", pending_publish_confidence_js)
        self.assertIn("Daily-use handoff: Pending Publish evidence decides whether it is sensible to press Drain Parked Outputs", pending_publish_confidence_js)
        self.assertIn("Scope boundary: Pending filters, selected rows, recovery dry-runs", pending_publish_confidence_js)
        self.assertIn("drain only after current parked rows, recovery dry-run, latest drain evidence, Completed/output proof, and diagnostics order agree.", pending_publish_confidence_js)
        self.assertIn("Mutation guardrail: this checklist cannot drain, repair, rewrite, move, delete, publish, accept outputs, write manifests, or bypass backend validation.", pending_publish_confidence_js)
        self.assertIn("pending-drain-decision-summary", html)
        self.assertIn("pending-drain-decision-detail", html)
        self.assertIn('statusNode.dataset.state = pendingDrainDecisionStatusState(decisionStatus)', pending_publish_confidence_js)
        self.assertIn("function renderPendingPostDrainTrust", pending_publish_confidence_js)
        self.assertIn("function pendingPostDrainTrustRows", pending_publish_confidence_js)
        self.assertIn("function pendingPostDrainTrustStatus", pending_publish_confidence_js)
        self.assertIn("Pending Publish post-drain trust review:", pending_publish_confidence_js)
        self.assertIn("a drain is trusted only when current parked rows, durable drain summary, recent drain events/logs, Completed output proof, and Sample Validation deferred-publish evidence agree.", pending_publish_confidence_js)
        self.assertIn("Blocking evidence rows:", pending_publish_confidence_js)
        self.assertIn("Do not trust this drain outcome yet.", pending_publish_confidence_js)
        self.assertIn("Mutation guardrail: this review is read-only and cannot drain, repair, rewrite, move, delete, publish, mark outputs complete, append validation records, or touch media.", pending_publish_confidence_js)
        _assert_namespace_export(self, pending_publish_view_js, "mediaPipelinePendingPublishView", "renderPendingPostDrainTrust")
        self.assertIn("pending-post-drain-trust-summary", html)
        self.assertIn("pending-post-drain-trust-detail", html)
        self.assertIn("pending-drain-guard-status", html)
        self.assertIn("pending-drain-guard-summary", html)
        self.assertIn('<h2>Pending Publish Guard Evidence</h2>', html)
        self.assertIn('<h2>Pending Publish Drain</h2>', html)
        self.assertIn("function pendingDrainGuardState", pending_publish_confidence_js)
        self.assertIn("function renderPendingDrainGuard", pending_publish_confidence_js)
        self.assertIn("Drain Parked Outputs blocked by WebView evidence", pending_publish_confidence_js)
        self.assertIn("Pending table filter:", pending_publish_confidence_js)
        self.assertIn("local filters do not narrow publish scope", pending_publish_confidence_js)
        self.assertIn("The backend will still perform authoritative validation before moving files. Continue?", pending_publish_confidence_js)
        self.assertIn("Mutation guardrail: this guard cannot drain, repair, rewrite, move, delete, publish, accept outputs, write manifests, or bypass backend validation.", pending_publish_confidence_js)
        self.assertIn("attempted=${data.attempted_count}", pending_publish_drain_js)
        self.assertIn("remaining=${data.remaining_count}", pending_publish_drain_js)
        self.assertIn("function getLastPendingPublishPayload", pending_publish_view_js)
        self.assertIn("renderCompletedPendingProof", pending_publish_view_js)
        self.assertIn("function requestPendingPublishOpen", pending_publish_diagnostics_js)
        self.assertIn("/api/pending-publish/open", pending_publish_diagnostics_js)
        self.assertIn("pending-recovery-plan-selected-button", html)
        self.assertIn("pending-recovery-plan-all-button", html)
        self.assertIn("pending-recovery-plan-status", html)
        self.assertIn("pending-recovery-plan-detail", html)
        self.assertIn("pending-recovery-plan-rows", html)
        self.assertIn("pending-recovery-plan-row-detail", html)
        self.assertIn("pending-recovery-plan-history", html)
        self.assertIn("function createPendingPublishRecoveryModule", pending_publish_recovery_js)
        self.assertIn("window.__pendingPublishRecoveryModule", pending_publish_recovery_js)
        self.assertIn("const pendingRecoveryModule = window.__pendingPublishRecoveryModule || {}", pending_publish_view_js)
        self.assertIn("delete window.__pendingPublishRecoveryModule", pending_publish_view_js)
        self.assertIn("pendingRecoveryModule.createPendingPublishRecoveryModule", pending_publish_view_js)
        self.assertIn("function requestPendingRecoveryPlan", pending_publish_recovery_js)
        self.assertIn("/api/pending-publish/recovery-plan", pending_publish_recovery_js)
        self.assertIn("pending_publish.recovery_plan_dry_run", pending_publish_recovery_js)
        self.assertIn("function renderPendingRecoveryPlanResult", pending_publish_recovery_js)
        self.assertIn("function renderPendingRecoveryPlanRows", pending_publish_recovery_js)
        self.assertIn("function pendingRecoveryPlanRowDetailLines", pending_publish_recovery_js)
        self.assertIn("Selected recovery-plan row:", pending_publish_recovery_js)
        self.assertIn("Mutation guardrail: this drilldown is read-only", pending_publish_recovery_js)
        self.assertIn("function renderPendingRecoveryPlanHistory", pending_publish_recovery_js)
        self.assertIn("function isPendingRecoveryPlanCommand", pending_publish_recovery_js)
        self.assertIn("Recovery plan is dry-run only", pending_publish_recovery_js)
        self.assertIn("renderPendingDrainGuard(getLastPendingPayload(), getLastPendingRows(), getLastPendingSnapshot()", pending_publish_recovery_js)
        self.assertIn("renderPendingRecoveryPlanHistory(commandHistory)", command_history_js)
        self.assertIn("renderPendingDrainGuard(undefined, undefined, undefined, commandHistory)", command_history_js)
        self.assertIn("requestPendingRecoveryPlan(\"selected\")", js)
        self.assertIn("requestPendingRecoveryPlan(\"all\")", js)
        self.assertIn("let pendingOpenInFlight = false", pending_publish_view_js)
        self.assertIn("function setPendingOpenBusy", pending_publish_diagnostics_js)
        self.assertIn("function rejectPendingOpenWhileBusy", pending_publish_diagnostics_js)
        self.assertIn("function renderPendingOpenHistory", pending_publish_diagnostics_js)
        self.assertIn("function isPendingOpenCommand", pending_publish_diagnostics_js)
        self.assertIn("Backend pending row keys and target allowlists remain the source of truth.", pending_publish_diagnostics_js)
        self.assertIn("Another pending publish open command is already in progress.", pending_publish_diagnostics_js)
        self.assertIn('data-open-target-row-actions="pending"', html)
        self.assertIn('targetDataset: "openPending"', js)
        self.assertIn("requestPendingPublishOpen", js)
        self.assertIn("Play Parked Output", js)
        self.assertIn("play_local_file", js)
        self.assertIn("window.mediaPipelineRenameLabels", rename_labels_js)
        self.assertIn("function renameStatusExplanation", rename_labels_js)
        self.assertIn("function renamePreviewSourceLabel", rename_labels_js)
        self.assertIn("function renameConfidenceExplanation", rename_labels_js)
        self.assertIn("function renameConfidenceLabel", rename_labels_js)
        self.assertNotIn("window.renameStatusExplanation = renameStatusExplanation", rename_labels_js)
        self.assertNotIn("window.renamePreviewSourceLabel = renamePreviewSourceLabel", rename_labels_js)
        self.assertNotIn("window.renameConfidenceExplanation = renameConfidenceExplanation", rename_labels_js)
        self.assertNotIn("window.renameConfidenceLabel = renameConfidenceLabel", rename_labels_js)
        self.assertIn("Pipeline TV preview", rename_labels_js)
        self.assertIn("Movie scrub filters", rename_labels_js)
        self.assertIn("window.mediaPipelineRenameHistoryView", rename_history_view_js)
        self.assertIn("function renderRenameApplyHistory", rename_history_view_js)
        self.assertIn("function isRenameApplyCommand", rename_history_view_js)
        self.assertNotIn("window.isRenameApplyCommand = isRenameApplyCommand", rename_history_view_js)
        self.assertNotIn("window.renameApplyHistoryLine = renameApplyHistoryLine", rename_history_view_js)
        self.assertNotIn("window.renderRenameApplyHistory = renderRenameApplyHistory", rename_history_view_js)
        self.assertIn("rename.apply", rename_history_view_js)
        self.assertIn("if (entries[0] && typeof renderRenameApplyResult === \"function\")", rename_history_view_js)
        self.assertIn("renderRenameApplyResult(entries[0])", rename_history_view_js)
        self.assertIn("Backend rename preview/apply remains the source of truth for filesystem changes.", rename_history_view_js)
        self.assertIn("window.mediaPipelineRenameView", rename_view_js)
        self.assertIn("mediaPipelineRenameLabels", rename_view_js)
        self.assertNotIn("window.renameStatusExplanation = renameStatusExplanation", rename_view_js)
        self.assertNotIn("window.renamePreviewSourceLabel = renamePreviewSourceLabel", rename_view_js)
        self.assertNotIn("window.renameConfidenceExplanation = renameConfidenceExplanation", rename_view_js)
        self.assertNotIn("window.renameConfidenceLabel = renameConfidenceLabel", rename_view_js)
        self.assertIn("mediaPipelineRenameHistoryView", rename_view_js)
        self.assertNotIn("window.isRenameApplyCommand = isRenameApplyCommand", rename_view_js)
        self.assertNotIn("window.renameApplyHistoryLine = renameApplyHistoryLine", rename_view_js)
        self.assertNotIn("window.renderRenameApplyHistory = renderRenameApplyHistory", rename_view_js)
        self.assertIn("function collectRenameRequest", rename_view_js)
        self.assertNotIn("movie_filter_terms_enabled", rename_view_js)
        self.assertIn("function renameCleaningFilterConfigPatch", rename_view_js)
        self.assertIn("RenameMovieFilterOptions: collectRenameMovieFilterOptions()", rename_view_js)
        self.assertIn("RenameMovieFilterTerms: collectRenameMovieFilterTerms()", rename_view_js)
        self.assertIn("RenameMovieRemoveTerms: parseRenameFilterTerms", rename_view_js)
        self.assertIn("RenameTVFilterOptions: collectRenameTvFilterOptions()", rename_view_js)
        self.assertIn("RenameTVFilterTerms: collectRenameTvFilterTerms()", rename_view_js)
        self.assertIn("RenameTVRemoveTerms: parseRenameFilterTerms", rename_view_js)
        self.assertIn("stageRenameCleaningFilterPatch(changes)", rename_view_js)
        self.assertIn("no backend save route was called", rename_view_js)
        self.assertIn("function collectRenameMovieFilterTerms", rename_view_js)
        self.assertIn("function collectRenameTvFilterTerms", rename_view_js)
        self.assertIn("movie_filter_terms_text: collectRenameMovieFilterTermsText()", rename_view_js)
        self.assertIn("tv_filter_terms_text: collectRenameTvFilterTermsText()", rename_view_js)
        self.assertIn('RENAME_FILTER_CATALOG_ROUTE = "/api/rename/cleaning-filters"', rename_view_js)
        self.assertIn('RENAME_MOVIE_FILTER_CATALOG_ROUTE = "/api/rename/movie-cleaning-filters"', rename_view_js)
        self.assertIn('RENAME_CLEAN_FILENAME_PREVIEW_ROUTE = "/api/rename/clean-filename-preview"', rename_view_js)
        self.assertIn("Source: backend clean_pipeline_movie_name.", rename_view_js)
        self.assertIn("Source: backend build_auto_tv_rename_name.", rename_view_js)
        self.assertIn("Saved filters affect future pipeline output naming", rename_view_js)
        self.assertIn("Movie filter policy:", rename_view_js)
        self.assertIn("TV filter policy:", rename_view_js)
        self.assertIn("function initRenameCleaningFilterEditorEvents", rename_view_js)
        self.assertIn("RENAME_CLEANING_FILTER_STORAGE_KEY", rename_view_js)
        self.assertIn("function saveRenameCleaningFiltersFromSettingsSave(", settings_view_js)
        self.assertIn("function mergeRenameCleaningFiltersForSave", settings_view_js)
        self.assertIn("function openSettingsSaveReviewDialog", settings_view_js)
        self.assertIn("renameView.saveRenameCleaningFilterDraft", settings_view_js)
        self.assertIn("Rename filters are included in the current Save Settings review.", settings_view_js)
        self.assertNotIn("settings-rename-use-editable-cleaning-filters", html)
        self.assertNotIn("Stage Rename Filter Patch", html)
        self.assertIn("settings-rename-filter-video-source", html)
        self.assertIn("settings-rename-filter-languages-subs-dubs", html)
        self.assertIn("settings-rename-filter-release-groups", html)
        self.assertIn("settings-rename-tv-filter-video-source", html)
        self.assertIn("settings-rename-tv-filter-release-groups", html)
        self.assertIn("settings-rename-tv-remove-terms", html)
        self.assertIn("settings-rename-preview-mode", html)
        self.assertIn("settings-rename-preview-source-folder", html)
        self.assertIn("settings-rename-preview-button", html)
        self.assertNotIn("settings-rename-cleaning-filters-save-button", html)
        self.assertIn("settings-rename-cleaning-filters-reset-button", html)
        self.assertIn("Rename Filter Case Log", html)
        self.assertIn("settings-rename-log-case-form", html)
        self.assertIn("settings-rename-log-case-source-folder", html)
        self.assertIn("settings-rename-log-case-source-file", html)
        self.assertIn("settings-rename-log-case-season-number", html)
        self.assertIn("settings-rename-log-case-expected-name", html)
        self.assertIn("settings-rename-log-case-expected-show", html)
        self.assertIn("settings-rename-log-case-expected-season", html)
        self.assertIn("settings-rename-log-case-status-select", html)
        self.assertIn("settings-rename-log-case-submit-button", html)
        self.assertIn("function settingsRenameLogCasePayload()", settings_view_js)
        self.assertIn("renameView.submitRenameBadCasePayload(payload)", settings_view_js)
        self.assertIn("initSettingsRenameLogCaseEvents()", settings_view_js)
        self.assertIn("function renameBatchSafetyLines", rename_view_js)
        self.assertIn("function renderRenameBatchSafety", rename_view_js)
        self.assertIn("function renderRenameReviewBoard", rename_view_js)
        self.assertIn("function renameReviewBoardLines", rename_view_js)
        self.assertIn("function renameReviewBoardStatus", rename_view_js)
        self.assertIn("function renamePreviewAggregateObject", rename_view_js)
        self.assertIn("function renameTemplateLabel", rename_view_js)
        self.assertIn("function renderRenameBulkEditor", rename_view_js)
        self.assertIn("function stageRenameBulkEdit", rename_view_js)
        self.assertIn("function usePipelineNamesForRenameScope", rename_view_js)
        self.assertIn("function setRenameBulkForce", rename_view_js)
        self.assertIn("function clearRenameBulkOverrides", rename_view_js)
        self.assertIn("function renameBulkScopeRows", rename_view_js)
        self.assertIn("Stage Bulk Edit uses the current backend preview final names", rename_view_js)
        self.assertIn("function renderRenameSelectionAudit", rename_view_js)
        self.assertIn("function renameSelectionAuditStatus", rename_view_js)
        self.assertIn("function renderRenameApplyReadiness", rename_view_js)
        self.assertIn("function renameApplyReadinessRows", rename_view_js)
        self.assertIn("function renameApplyReadinessStatus", rename_view_js)
        self.assertIn("function renameApplyScopeBlockers", rename_view_js)
        self.assertIn("const RENAME_PREVIEW_RENDER_LIMIT = 250", rename_view_js)
        self.assertIn("function renameRenderedRowsCount", rename_view_js)
        self.assertIn("Render cap visibility", rename_view_js)
        self.assertIn("checked scope may include rows not currently rendered", rename_view_js)
        self.assertIn("Rename selection is blocked by apply readiness", rename_view_js)
        self.assertIn("Apply posts confirm_apply plus selected_sources", rename_view_js)
        self.assertIn("backend rename.apply remains the only filesystem mutation path", rename_view_js)
        self.assertIn("rename-apply-readiness-rows", html)
        self.assertIn("rename-apply-readiness-status", html)
        self.assertIn("Preview before apply", html)
        self.assertIn("function renameApplyResultLines", rename_view_js)
        self.assertIn("function renderRenameApplyResult", rename_view_js)
        self.assertIn("rename-apply-progress-bars", html)
        self.assertIn("function renameApplyProgressBars", rename_view_js)
        self.assertIn("function renderRenameApplyProgress", rename_view_js)
        self.assertIn('renderProgressBarsInto("rename-apply-progress-bars"', rename_view_js)
        self.assertIn("rename-apply-outcome-status", html)
        self.assertIn("rename-apply-outcome-summary", html)
        self.assertIn("rename-apply-outcome-rows", html)
        self.assertIn("Outcome Checkpoint", html)
        self.assertIn("function renderRenameApplyOutcomeReview", rename_view_js)
        self.assertIn("function renameApplyOutcomeRows", rename_view_js)
        self.assertIn("function renameApplyOutcomeStatus", rename_view_js)
        self.assertIn("Backend rename apply outcome review:", rename_view_js)
        self.assertIn("Undo / rollback evidence", rename_view_js)
        self.assertIn("Only /api/rename/apply can mutate files", rename_view_js)
        self.assertIn("Change kind:", rename_view_js)
        self.assertIn("Sidecar moves planned:", rename_view_js)
        self.assertIn("Undo manifest:", rename_view_js)
        self.assertIn("TV ordering: backend preview follows the current Paths textarea order.", rename_view_js)
        self.assertIn("Preview-wide review board.", rename_view_js)
        self.assertIn("template_preset", rename_view_js)
        self.assertIn("active_template", rename_view_js)
        self.assertIn("template_catalog", rename_view_js)
        self.assertIn("confidence_counts", rename_view_js)
        self.assertIn("preview_source_counts", rename_view_js)
        self.assertIn("change_kind_counts", rename_view_js)
        self.assertIn("Backend rename preview/apply remains the source of truth for filesystem changes.", rename_view_js)
        self.assertIn("/api/rename/browse", rename_view_js)
        self.assertIn("function browseRenamePaths", rename_view_js)
        self.assertIn("Windows file browser", rename_view_js)
        self.assertIn("Rename path browser route is not available in the running backend", rename_view_js)
        self.assertIn("function renderRenamePreview", rename_view_js)
        self.assertIn("function renderRenameSummary", rename_view_js)
        self.assertIn("Preview source:", rename_view_js)
        self.assertIn("Confidence reason(s):", rename_view_js)
        self.assertIn("Checked-row apply still rebuilds the plan through the backend", rename_view_js)
        self.assertIn("function getCheckedRenameRows", rename_view_js)
        self.assertIn("function checkApplicableRenameRows", rename_view_js)
        self.assertIn("function clearCheckedRenameRows", rename_view_js)
        self.assertIn("function moveCheckedRenamePaths", rename_view_js)
        self.assertIn("function naturalSortRenamePaths", rename_view_js)
        self.assertIn("Run Preview to rebuild TV sequence numbering", rename_view_js)
        self.assertIn("checked rows are required and are sent as selected_sources", rename_view_js)
        self.assertIn("function applyRenameSelectedOverride", rename_view_js)
        self.assertIn("function clearRenameSelectedOverride", rename_view_js)
        self.assertIn("function selectRenameRow", rename_view_js)
        self.assertIn("visibleResult = { ...result, request }", rename_view_js)
        self.assertIn("let renamePreviewRequestId = 0", rename_view_js)
        self.assertIn("let renamePreviewInFlight = false", rename_view_js)
        self.assertIn("let renameBrowseInFlight = false", rename_view_js)
        self.assertIn("let renameApplyInFlight = false", rename_view_js)
        self.assertIn("function setRenamePreviewBusy", rename_view_js)
        self.assertIn("function setRenameApplyBusy", rename_view_js)
        self.assertIn("function syncRenameCommandButtons", rename_view_js)
        removed_rename_flat_exports = [
            "refreshRenamePreview",
            "renderRenameBulkEditor",
            "stageRenameBulkEdit",
            "usePipelineNamesForRenameScope",
            "setRenameBulkForce",
            "clearRenameBulkOverrides",
            "syncRenameCommandButtons",
            "checkApplicableRenameRows",
            "clearCheckedRenameRows",
            "moveCheckedRenamePaths",
            "naturalSortRenamePaths",
            "renderRenameFileSourceSummary",
            "useSelectedQueueRowForRename",
            "useLoadedQueueRowsForRename",
            "addRenamePathFromInput",
            "clearRenamePaths",
            "applyRenameSelectedOverride",
            "clearRenameSelectedOverride",
        ]
        for export_name in removed_rename_flat_exports:
            self.assertNotIn(f"window.{export_name} =", rename_view_js)
        self.assertIn('"rename-preview-button"', rename_view_js)
        self.assertIn('"rename-preview-top-button"', rename_view_js)
        self.assertIn("if (renamePreviewInFlight || renameApplyInFlight)", rename_view_js)
        self.assertIn("setRenameApplyBusy(true)", rename_view_js)
        self.assertIn("renamePreviewInFlight || renameBrowseInFlight || renameApplyInFlight", rename_view_js)
        self.assertIn("requestId !== activeRenamePreviewRequestId", rename_view_js)
        self.assertIn("/api/rename/apply", rename_view_js)
        self.assertIn("confirm_apply", rename_view_js)
        self.assertIn("const renameView = window.mediaPipelineRenameView || {}", js)
        self.assertIn("renameView.checkApplicableRenameRows?.()", js)
        self.assertIn("renameView.clearCheckedRenameRows?.()", js)
        self.assertIn("renameView.moveCheckedRenamePaths?.(-1)", js)
        self.assertIn("renameView.moveCheckedRenamePaths?.(1)", js)
        self.assertIn("renameView.naturalSortRenamePaths?.()", js)
        self.assertIn("initRenameCleaningFilterEditorEvents", js)
        self.assertIn("renameView.stageRenameBulkEdit?.()", js)
        self.assertIn("renameView.setRenameBulkForce?.(true)", js)
        self.assertIn("renameView.clearRenameBulkOverrides?.()", js)
        self.assertIn("String(item?.source || \"\").toLowerCase()", rename_view_js)
        self.assertNotIn("toLocaleLowerCase", rename_view_js)
        self.assertIn("function queueWorkflowStatus", queue_view_js)
        self.assertIn("function queueWorkflowLines", queue_view_js)
        self.assertIn("function queueReviewStatus", queue_view_js)
        self.assertIn("Flagged rows:", queue_view_js)
        self.assertIn("launch, queue mutation, rerun, and file actions remain backend-owned", queue_view_js)
        self.assertIn("Cross-page workflow: Queue", queue_view_js)
        self.assertIn("backend launch commands remain backend-owned", queue_view_js)
        self.assertIn("Diagnostics > State Artifact Summary, Queue Snapshot", queue_view_js)
        self.assertIn("appendDiagnosticsBridgeButton(container, actions", queue_view_js)
        self.assertIn("Diagnostics bridge: Review in Diagnostics switches", queue_view_js)
        self.assertIn("function completedWorkflowStatus", completed_view_review_js)
        self.assertIn("function completedWorkflowLines", completed_view_review_js)
        self.assertIn("function completedReviewStatus", completed_view_review_js)
        self.assertIn("Flagged rows:", completed_view_review_js)
        self.assertIn("repair, reconcile, rerun, cleanup, and file deletion remain backend-owned", completed_view_review_js)
        self.assertIn("Cross-page workflow: Completed", completed_view_review_js)
        self.assertIn("check Pending Publish before rerun", completed_view_review_js)
        self.assertIn("Repair, rerun, cleanup, and reconcile actions remain backend-owned", completed_view_review_js)
        self.assertIn("appendDiagnosticsBridgeButton(container, actions", completed_view_diagnostics_js)
        self.assertIn("Diagnostics bridge: Review in Diagnostics switches", completed_view_diagnostics_js)
        self.assertIn("function pendingWorkflowStatus", pending_publish_view_js)
        self.assertIn("function pendingWorkflowLines", pending_publish_view_js)
        self.assertIn("function pendingReviewStatus", pending_publish_view_js)
        self.assertIn("Flagged rows:", pending_publish_view_js)
        self.assertIn("drain, repair, rewrite, move, delete, and publish actions remain backend-owned", pending_publish_view_js)
        self.assertIn("Cross-page workflow: Pending Publish", pending_publish_view_js)
        self.assertIn("Drain Parked Outputs remains backend-owned", pending_publish_view_js)
        self.assertIn("appendDiagnosticsBridgeButton(container, actions", pending_publish_diagnostics_js)
        self.assertIn("Diagnostics bridge: Review in Diagnostics switches", pending_publish_diagnostics_js)
        self.assertIn("window.mediaPipelineSettingsOverview", settings_overview_js)
        self.assertIn("function renderSettingsOverview", settings_overview_js)
        self.assertIn("function buildSettingsOverviewRows", settings_overview_js)
        self.assertIn("function settingsOperatorTrustLines", settings_overview_js)
        self.assertIn("function renderSettingsOperatorTrust", settings_overview_js)
        self.assertIn("Saved settings trust checklist:", settings_overview_js)
        self.assertIn("Source safety:", settings_overview_js)
        self.assertIn("Publish behavior:", settings_overview_js)
        self.assertIn("Remux/encode routing:", settings_overview_js)
        self.assertIn("Subtitle routing:", settings_overview_js)
        for flat_settings_overview_export in (
            "window.configValue =",
            "window.buildSettingsOverviewRows =",
            "window.renderSettingsOverview =",
            "window.settingsOperatorTrustStatus =",
            "window.renderSettingsOperatorTrust =",
        ):
            self.assertNotIn(flat_settings_overview_export, settings_overview_js)
        self.assertIn("Audio routing:", settings_overview_js)
        self.assertIn("Mutation guardrail: settings trust is read-only", settings_overview_js)
        self.assertIn("window.mediaPipelineSettingsCommandHistory", settings_command_history_js)
        self.assertIn("function isSettingsCommand", settings_command_history_js)
        self.assertIn("function renderSettingsCommandHistory", settings_command_history_js)
        self.assertIn("function settingsCommandHistoryLine", settings_command_history_js)
        self.assertNotIn("window.isSettingsCommand = isSettingsCommand", settings_command_history_js)
        self.assertNotIn("window.settingsCommandHistoryLine = settingsCommandHistoryLine", settings_command_history_js)
        self.assertNotIn("window.renderSettingsCommandHistory = renderSettingsCommandHistory", settings_command_history_js)
        self.assertIn("settings.browse_path", settings_command_history_js)
        self.assertIn("settings.preview_patch", settings_command_history_js)
        self.assertIn("settings.save_patch", settings_command_history_js)
        self.assertIn("renderCompactCommandHistoryBlock({", settings_command_history_js)
        self.assertIn("Backend settings patch validation/save remains the source of truth.", settings_command_history_js)
        self.assertIn("function settingsLaunchImpactRows", settings_view_js)
        self.assertIn("function settingsLaunchImpactStatus", settings_view_js)
        self.assertIn("function settingsLaunchImpactSummaryLines", settings_view_js)
        self.assertIn("function renderSettingsLaunchImpactHandoffFromEntries", settings_view_js)
        self.assertIn("Backend media-policy readiness", launch_view_risk_js)
        self.assertIn("Backend media-policy readiness", cross_page_settings_js)
        self.assertIn("media readiness=", cross_page_settings_js)
        self.assertIn("media_policy_readiness", launch_view_risk_js)
        self.assertIn("settingsBackendPolicyImpact", settings_view_js)
        self.assertIn("settings_policy_impact.v1", settings_policy_impact_js)
        self.assertIn("settingsBackendPolicyImpact", settings_policy_impact_js)
        self.assertIn("settings_launch_risk_handoff.v1", launch_view_risk_js)
        self.assertIn("launchSettingsBackendRiskRows", launch_view_risk_js)
        self.assertIn('settingsPolicyImpactDo("renderSettingsLaunchImpactHandoffFromEntries", [entries])', settings_view_js)
        self.assertIn("Launch uses saved backend settings, not unsaved edits.", settings_view_js)
        self.assertIn("backend launch validation remains authoritative", settings_view_js)
        self.assertIn("window.settingsLaunchImpactRows = settingsLaunchImpactRows", settings_view_js)
        self.assertIn("let settingsPatchTouched = false", settings_view_js)
        self.assertIn("/api/settings/browse-path", settings_view_js)
        self.assertIn("function browseSettingsPath", settings_view_js)
        self.assertIn("settings-file-safety-source-movies-browse", html)
        self.assertIn("data-settings-path-key=\"SourceMovies\"", html)
        self.assertIn("data-settings-path-key=\"Outsource\"", html)
        self.assertIn("backend-owned Windows folder picker", settings_view_js)
        self.assertIn("It cannot save settings, launch work, rewrite queue state, publish, rename, delete, or touch media files.", settings_view_js)
        self.assertIn("function settingsPatchEffectiveChangedEntries", settings_view_js)
        self.assertIn("function settingsPatchHasUnsavedChanges", settings_view_js)
        _assert_namespace_export(self, settings_view_js, "mediaPipelineSettingsView", "settingsPatchHasUnsavedChanges")
        self.assertIn("lastSettingsPatchPreviewEvidence", settings_view_js)
        self.assertIn("lastSettingsPatchSaveEvidence", settings_view_js)
        self.assertIn("function settingsStableJsonValue", settings_view_js)
        self.assertIn("function settingsPatchSignature", settings_view_js)
        self.assertIn("function settingsBackendResultRows", settings_backend_result_js)
        self.assertIn("function settingsBackendResultRowKey", settings_backend_result_js)
        self.assertIn("function settingsBackendResultDetailLines", settings_backend_result_js)
        self.assertIn("function renderSettingsBackendResultFromEntries", settings_backend_result_js)
        self.assertIn("settings-backend-result-rows", html)
        self.assertIn("settings-backend-result-detail", html)
        self.assertIn("Save candidate identity:", settings_backend_result_js)
        self.assertIn("Redacted diff lines:", settings_backend_result_js)
        self.assertIn("Evidence matches current JSON:", settings_backend_result_js)
        self.assertIn("Backend data JSON", settings_backend_result_js)
        self.assertIn("jsonDetailText({", settings_backend_result_js)
        self.assertIn("Backend save handoff:", settings_backend_result_js)
        self.assertIn("Save Settings will review the current values before writing.", settings_backend_result_js)
        self.assertIn("Save Settings is the persistence command", settings_backend_result_js)
        self.assertIn("The backend save command requires confirm_save=true", settings_backend_result_js)
        self.assertIn("Launch uses saved backend settings only", settings_backend_result_js)
        self.assertIn("Only backend command results count as persistence evidence.", settings_view_js)
        _assert_namespace_export(self, settings_view_js, "mediaPipelineSettingsView", "settingsBackendResultRows")
        _assert_namespace_export(self, settings_view_js, "mediaPipelineSettingsView", "settingsBackendResultDetailLines")
        self.assertIn("renderAllLaunchPreflights", settings_view_js)
        self.assertIn("function launchUnsavedSettingsPatchLines", launch_view_risk_js)
        self.assertIn("Unsaved Settings changes:", launch_view_risk_js)
        self.assertIn("Launch uses saved backend settings only.", launch_view_risk_js)
        self.assertIn("Save-candidate media-policy delta:", launch_view_risk_js)
        self.assertIn("settingsPolicyDeltaRows", launch_view_risk_js)
        self.assertIn("settingsPolicyDeltaStatus", launch_view_risk_js)
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchUnsavedSettingsPatchLines")
        self.assertIn("window.mediaPipelineSettingsMetadata", settings_metadata_js)
        self.assertIn("settingsBuilderFields", settings_metadata_js)
        self.assertIn("fileSafetySettingsBuilderFields", settings_metadata_js)
        self.assertIn("networkSettingsBuilderFields", settings_metadata_js)
        self.assertIn("queueSettingsBuilderFields", settings_metadata_js)
        self.assertIn("videoDetailSettingsBuilderFields", settings_metadata_js)
        self.assertIn("runtimeSettingsBuilderFields", settings_metadata_js)
        self.assertIn("pendingPublishSettingsBuilderFields", settings_metadata_js)
        self.assertIn("subtitleSettingsBuilderFields", settings_metadata_js)
        self.assertIn("audioSettingsBuilderFields", settings_metadata_js)
        self.assertIn("settingsSafetyLockDefinitions", settings_metadata_js)
        self.assertIn("settingsImpactGroups", settings_metadata_js)
        self.assertIn("settingsSpecificImpactHints", settings_metadata_js)
        self.assertIn("settingsChoiceLabels", settings_metadata_js)
        self.assertIn("settings-runtime-cleanup-scan-timeout", settings_metadata_js)
        self.assertIn("settings-file-safety-valid-extensions", settings_metadata_js)
        self.assertIn("settings-file-safety-robocopy-flags", settings_metadata_js)
        self.assertIn("settings-runtime-log-retention", settings_metadata_js)
        self.assertIn("Source deletion must remain an explicit opt-in safety decision.", settings_metadata_js)
        self.assertIn("Source deletion is off. Normal processing should copy to scratch and preserve sources.", settings_metadata_js)
        self.assertIn("PATH fallback is enabled. Runs may silently use system FFmpeg", settings_metadata_js)
        self.assertIn(
            "Per-worker overrides are configured, but backend policy currently ignores them for worker encode snapshots.",
            settings_metadata_js,
        )
        self.assertIn("Robocopy transfer flags affect retry behavior", settings_metadata_js)
        self.assertIn("Plex direct/stream", settings_metadata_js)
        self.assertIn("Queue / reprocess", settings_metadata_js)
        self.assertIn("Paths / file safety", settings_metadata_js)
        self.assertIn("Runtime / diagnostics", settings_metadata_js)
        self.assertIn("Pending publish / recovery", settings_metadata_js)
        self.assertIn("settings-pending-robocopy-timeout", settings_metadata_js)
        self.assertIn("completed payloads can park", settings_metadata_js)
        self.assertIn("scan cadence, subprocess timeout ceilings", settings_metadata_js)
        self.assertIn("window.mediaPipelineSettingsView", settings_view_js)
        self.assertIn("const settingsMetadata = window.mediaPipelineSettingsMetadata", settings_view_js)
        self.assertIn("function renderSettingsRows", settings_view_js)
        self.assertIn("function settingsRawTriageRows", settings_view_js)
        self.assertIn("function settingsRawTriageStatus", settings_view_js)
        self.assertIn("function renderSettingsRawTriage", settings_view_js)
        self.assertIn("function settingsRawTriageDetailLines", settings_view_js)
        self.assertIn("function settingsRawActionPlanRows", settings_view_js)
        self.assertIn("function settingsRawActionPlanStatus", settings_view_js)
        self.assertIn("function settingsRawActionPlanDetailLines", settings_view_js)
        self.assertIn("function renderSettingsRawActionPlan", settings_view_js)
        self.assertIn("function settingsSafetyLockRows", settings_view_js)
        self.assertIn("function renderSettingsSafetyLocks", settings_view_js)
        self.assertIn("Settings raw-key triage:", settings_view_js)
        self.assertIn("Unknown raw keys:", settings_view_js)
        self.assertIn("Mutation guardrail: this triage is read-only", settings_view_js)
        self.assertIn("Settings raw-key action plan:", settings_view_js)
        self.assertIn("BDPGS OCR path evidence", settings_view_js)
        self.assertIn("VobSub OCR path evidence", settings_view_js)
        self.assertIn("Network auth secrets", settings_view_js)
        self.assertIn("No raw-key action-plan row selected.", settings_view_js)
        self.assertIn("Settings safety lock review:", settings_view_js)
        self.assertIn("Mutation guardrail: this panel is read-only", settings_view_js)
        self.assertIn("__settingsRawTriageModule", settings_view_raw_triage_js)
        self.assertIn("__settingsSafetyLocksModule", settings_view_safety_locks_js)
        self.assertIn("const settingsRawTriageModule = window.__settingsRawTriageModule || {}", settings_view_parent_js)
        self.assertIn("const settingsSafetyLocksModule = window.__settingsSafetyLocksModule || {}", settings_view_parent_js)
        self.assertIn("function renderSettings", settings_view_js)
        self.assertIn("function getLastSettings", settings_view_js)
        self.assertIn("function initSettingsViewEvents", settings_view_js)
        self.assertIn("syncSettingsBuilderFromConfig", settings_view_js)
        self.assertIn("collectSettingsBuilderPatch", settings_view_js)
        self.assertIn("applySettingsBuilderToPatch", settings_view_js)
        self.assertIn("refreshSettingsBuilderChoices", settings_view_js)
        self.assertIn("renderSettingsBuilderGuidance", settings_view_js)
        self.assertIn("markSettingsBuilderDirty", settings_view_js)
        self.assertIn("videoDetailSettingsBuilderFields", settings_view_js)
        self.assertIn("collectVideoDetailSettingsBuilderPatch", settings_view_js)
        self.assertIn("applyVideoDetailSettingsBuilderToPatch", settings_view_js)
        self.assertIn("renderVideoDetailSettingsBuilderGuidance", settings_view_js)
        self.assertIn("__settingsViewVideoBuilderModule", settings_view_video_builder_js)
        self.assertIn("RemuxSafeVideoCodecs", settings_view_video_builder_js)
        self.assertIn("FallbackCpuQuality", settings_view_video_builder_js)
        self.assertIn("legacy raw FFmpeg flags should normally stay empty", settings_view_video_builder_js)
        self.assertIn("lastSettingsFieldDefinitions", settings_view_js)
        self.assertIn("fileSafetySettingsBuilderFields", settings_view_js)
        self.assertIn("collectFileSafetySettingsBuilderPatch", settings_view_js)
        self.assertIn("applyFileSafetySettingsBuilderToPatch", settings_view_js)
        self.assertIn("renderFileSafetySettingsBuilderGuidance", settings_view_js)
        self.assertIn("__settingsViewFileSafetyBuilderModule", settings_view_file_safety_builder_js)
        self.assertIn("SourceMovies", settings_view_file_safety_builder_js)
        self.assertIn("OutputSizeMultiplier", settings_view_file_safety_builder_js)
        self.assertIn("RobocopyFlags", settings_view_file_safety_builder_js)
        self.assertIn("pipeline should copy source files to scratch", settings_view_file_safety_builder_js)
        self.assertIn("high robocopy thread counts can saturate", settings_view_file_safety_builder_js)
        self.assertIn("corrupt or partially-written sources may pass discovery", settings_view_file_safety_builder_js)
        self.assertIn("networkSettingsBuilderFields", settings_view_js)
        self.assertIn("collectNetworkSettingsBuilderPatch", settings_view_js)
        self.assertIn("applyNetworkSettingsBuilderToPatch", settings_view_js)
        self.assertIn("renderNetworkSettingsBuilderGuidance", settings_view_js)
        self.assertIn("__settingsViewNetworkBuilderModule", settings_view_network_builder_js)
        self.assertIn("NetworkRole", settings_view_network_builder_js)
        self.assertIn("CoordinatorPort", settings_view_network_builder_js)
        self.assertIn("WorkerSourcePathMap", settings_view_network_builder_js)
        self.assertIn("Secret guardrail", settings_view_network_builder_js)
        self.assertIn("openNetworkRoleSetup", settings_view_network_builder_js)
        self.assertIn("Coordinator/worker runtime command controls remain backend-owned", settings_view_network_builder_js)
        self.assertIn("Validate path rewrites on the worker", settings_view_network_builder_js)
        self.assertIn("queueSettingsBuilderFields", settings_view_js)
        self.assertIn("collectQueueSettingsBuilderPatch", settings_view_js)
        self.assertIn("applyQueueSettingsBuilderToPatch", settings_view_js)
        self.assertIn("renderQueueSettingsBuilderGuidance", settings_view_js)
        self.assertIn("__settingsViewQueueBuilderModule", settings_view_queue_builder_js)
        self.assertIn("PriorityMarkers", settings_view_queue_builder_js)
        self.assertIn("ProcessedIndexRefreshSeconds", settings_view_queue_builder_js)
        self.assertIn("ReprocessAll", settings_view_queue_builder_js)
        self.assertIn("queue mutation and processing starts remain backend-owned", settings_view_queue_builder_js)
        self.assertIn("backend risk preview should flag this", settings_view_queue_builder_js)
        self.assertIn("zero disables processed-index caching", settings_view_queue_builder_js)
        self.assertIn("runtimeSettingsBuilderFields", settings_view_js)
        self.assertIn("collectRuntimeSettingsBuilderPatch", settings_view_js)
        self.assertIn("applyRuntimeSettingsBuilderToPatch", settings_view_js)
        self.assertIn("renderRuntimeSettingsBuilderGuidance", settings_view_js)
        self.assertIn("__settingsViewRuntimeBuilderModule", settings_view_runtime_builder_js)
        self.assertIn("FFmpegEncodeTimeoutSeconds", settings_view_runtime_builder_js)
        self.assertIn("AllowSystemTools", settings_view_runtime_builder_js)
        self.assertIn("long-running process ceilings", settings_view_runtime_builder_js)
        self.assertIn("release validation should normally use bundled tools", settings_view_runtime_builder_js)
        self.assertIn("zero-day retention can remove forensic logs quickly", settings_view_runtime_builder_js)
        self.assertIn("pendingPublishSettingsBuilderFields", settings_view_js)
        self.assertIn("syncPendingPublishSettingsBuilderFromConfig", settings_view_js)
        self.assertIn("collectPendingPublishSettingsBuilderPatch", settings_view_js)
        self.assertIn("applyPendingPublishSettingsBuilderToPatch", settings_view_js)
        self.assertIn("renderPendingPublishSettingsBuilderGuidance", settings_view_js)
        self.assertIn("__settingsViewPendingPublishBuilderModule", settings_view_pending_builder_js)
        self.assertIn("DeferredPublish", settings_view_pending_builder_js)
        self.assertIn("CleanupRemoteStaging", settings_view_pending_builder_js)
        self.assertIn("Drain Parked Outputs", settings_view_pending_builder_js)
        self.assertIn("direct publish plus skipped stability checks", settings_view_pending_builder_js)
        self.assertIn("high robocopy thread counts can saturate pending-publish drains", settings_view_pending_builder_js)
        self.assertIn("subtitleSettingsBuilderFields", settings_view_js)
        self.assertIn("syncSubtitleSettingsBuilderFromConfig", settings_view_js)
        self.assertIn("collectSubtitleSettingsBuilderPatch", settings_view_js)
        self.assertIn("applySubtitleSettingsBuilderToPatch", settings_view_js)
        self.assertIn("renderSubtitleSettingsBuilderGuidance", settings_view_js)
        self.assertIn("settingsBdpgsOcrPathEvidence", settings_view_js)
        self.assertIn("renderSettingsBdpgsOcrPathEvidence", settings_view_js)
        self.assertIn("settingsVobSubOcrPathEvidence", settings_view_js)
        self.assertIn("renderSettingsVobSubOcrPathEvidence", settings_view_js)
        self.assertIn("__settingsViewSubtitleBuilderModule", settings_view_subtitle_builder_js)
        self.assertIn("Saved BDPGS OCR path evidence:", settings_view_subtitle_builder_js)
        self.assertIn("Saved VobSub OCR path evidence:", settings_view_subtitle_builder_js)
        self.assertIn("WebView does not resolve arbitrary paths or run OCR", settings_view_subtitle_builder_js)
        self.assertIn("Default policy: original subtitle tracks are preserved", settings_view_subtitle_builder_js)
        self.assertIn("Subtitle routing summary:", settings_view_subtitle_builder_js)
        self.assertIn('byId("settings-subtitle-languages")', settings_view_subtitle_builder_js)
        self.assertIn("ConvertTx3gToSrt", settings_view_subtitle_builder_js)
        self.assertIn(
            'setSubtitleBuilderControl("settings-subtitle-convert-bdpgs", "ConvertBdpgsToSrt", "bool", false)',
            settings_view_subtitle_builder_js,
        )
        self.assertIn(
            'settingsMediaPolicyBool("settings-subtitle-convert-bdpgs", "ConvertBdpgsToSrt", false)',
            settings_policy_impact_js,
        )
        self.assertIn('settingsPatchCandidateBool(entries, "ConvertBdpgsToSrt", false)', settings_policy_impact_js)
        self.assertIn('settingsPatchCurrentBool("ConvertBdpgsToSrt", false)', settings_policy_impact_js)
        self.assertIn('launchSettingsConfigValue(config, "ConvertBdpgsToSrt"), false', launch_view_risk_js)
        self.assertIn(
            'launchPolicyCandidateValue(config, entryMap, "ConvertBdpgsToSrt", false), false',
            launch_view_risk_js,
        )
        self.assertIn("preferred-language TX3G/mov_text subtitles will not generate SRT without conversion enabled.", settings_view_subtitle_builder_js)
        self.assertIn("Drop TX3G is enabled while Convert TX3G to SRT is disabled.", settings_view_subtitle_builder_js)
        self.assertIn("writeSettingsPatchJson", settings_view_js)
        self.assertIn("audioSettingsBuilderFields", settings_view_js)
        self.assertIn("syncAudioSettingsBuilderFromConfig", settings_view_js)
        self.assertIn("collectAudioSettingsBuilderPatch", settings_view_js)
        self.assertIn("applyAudioSettingsBuilderToPatch", settings_view_js)
        self.assertIn("renderAudioSettingsBuilderGuidance", settings_view_js)
        self.assertIn("AudioTranscodeAutoBitrateByChannels", settings_metadata_js)
        self.assertIn("__settingsViewAudioBuilderModule", settings_view_audio_builder_js)
        self.assertIn("Audio routing summary:", settings_view_audio_builder_js)
        self.assertIn("settings-audio-auto-bitrate", settings_view_audio_builder_js)
        self.assertIn("Default policy: keep no-audio output disabled", settings_view_audio_builder_js)
        self.assertIn("no-audio outputs can publish files Plex users may treat as broken", settings_view_audio_builder_js)
        self.assertIn("custom codec list makes copy-vs-transcode depend on the manual codec list", settings_view_audio_builder_js)
        self.assertIn("function settingsMediaPolicyRows", settings_view_js)
        self.assertIn("function renderSettingsMediaPolicyCrossCheck", settings_view_js)
        self.assertIn("function settingsBackendMediaPolicyReadiness", settings_view_js)
        self.assertIn("function renderSettingsBackendMediaPolicyReadiness", settings_view_js)
        self.assertIn("function settingsActiveMediaPolicyRows", settings_view_js)
        self.assertIn("function renderSettingsActiveMediaPolicyHandoff", settings_view_js)
        self.assertIn("Backend media-policy readiness:", settings_view_js)
        self.assertIn("settings-backend-media-policy-rows", html)
        self.assertIn("Policy Readiness", html)
        self.assertIn("media_policy_readiness", settings_overview_js)
        self.assertIn("Audio / subtitle policy cross-check:", settings_view_js)
        self.assertIn("SRT creation, original-track preservation, language routing, and audio predictability", settings_view_js)
        self.assertIn("Save Settings remains backend-owned; this panel does not change FFmpeg", settings_view_js)
        self.assertIn("Active media-policy handoff:", settings_view_js)
        self.assertIn("Builder edits are not launch-active until backend Save succeeds", settings_view_js)
        self.assertIn("Plex-compatible H.264 sources can remain copy/remux candidates", settings_view_js)
        self.assertIn("MP4 cannot carry every original subtitle format", settings_view_js)
        _assert_namespace_export(self, settings_view_js, "mediaPipelineSettingsView", "renderSettingsActiveMediaPolicyHandoff")
        self.assertIn("Do not drop TX3G while conversion is disabled", settings_view_js)
        self.assertIn("Do not drop BDPGS while OCR is disabled", settings_view_js)
        self.assertIn("settings-builder-routing-profile", settings_view_js)
        self.assertIn("settings-builder-size-guard", settings_view_js)
        self.assertIn("reloadSettingsFromDisk", settings_view_js)
        self.assertIn("const settingsCommandButtonIds", settings_view_js)
        self.assertIn("function setSettingsCommandBusy", settings_view_js)
        self.assertIn("function rejectSettingsCommandWhileBusy", settings_view_js)
        self.assertIn("Another settings command is already in progress.", settings_view_js)
        self.assertIn("mediaPipelineSettingsCommandHistory", settings_view_js)
        self.assertNotIn("window.isSettingsCommand = isSettingsCommand", settings_view_js)
        self.assertNotIn("window.settingsCommandHistoryLine = settingsCommandHistoryLine", settings_view_js)
        self.assertNotIn("window.renderSettingsCommandHistory = renderSettingsCommandHistory", settings_view_js)
        self.assertIn("previewSettingsPatch", settings_view_js)
        self.assertIn("let settingsPatchPreviewRequestId = 0", settings_view_js)
        self.assertIn("const rawAtRequest = raw", settings_view_js)
        self.assertIn("requestId !== settingsPatchPreviewRequestId", settings_view_js)
        self.assertIn("Preview replaced", settings_view_js)
        self.assertIn("saveSettingsPatch", settings_view_js)
        self.assertIn("settings-save-progress-bars", html)
        self.assertIn("function settingsCommandProgressBars", settings_view_js)
        self.assertIn("function renderSettingsSaveProgress", settings_view_js)
        self.assertIn('renderProgressBarsInto("settings-save-progress-bars"', settings_view_js)
        self.assertIn("Settings save/reload progress:", settings_view_js)
        self.assertIn("appendSettingsRiskSummaryLines", settings_view_js)
        self.assertIn("Risk summary:", settings_view_js)
        self.assertIn("risk_summary", settings_view_js)
        self.assertIn("renderSettingsPatchSummary", settings_view_js)
        self.assertIn("function settingsPatchImpactEntries", settings_view_js)
        self.assertIn("function renderSettingsPatchImpactSummaryFromEntries", settings_view_js)
        self.assertIn("function settingsPatchSaveReadinessIssues", settings_view_js)
        self.assertIn("function renderSettingsPatchSaveReadinessFromEntries", settings_view_js)
        self.assertIn("function settingsPolicyDeltaRows", settings_view_js)
        self.assertIn("function renderSettingsPolicyDeltaFromEntries", settings_view_js)
        self.assertIn("Save-candidate media-policy delta:", settings_view_js)
        self.assertIn("This compares current saved values against the local save candidate", settings_view_js)
        self.assertIn("renderSettingsPolicyDeltaFromEntries(impactEntries)", settings_view_js)
        self.assertIn("function settingsEffectivePolicyRows", settings_view_js)
        self.assertIn("function settingsEffectivePolicyTrustStatus", settings_view_js)
        self.assertIn("function renderSettingsEffectivePolicyTrustFromEntries", settings_view_js)
        self.assertIn("Effective policy trust summary:", settings_view_js)
        self.assertIn("Launch-active policy is the saved backend config", settings_view_js)
        self.assertIn("WebView builder edits are candidates only", settings_view_js)
        self.assertIn("renderSettingsEffectivePolicyTrustFromEntries(impactEntries)", settings_view_js)
        _assert_namespace_export(self, settings_view_js, "mediaPipelineSettingsView", "settingsEffectivePolicyRows")
        self.assertIn("settings-patch-impact-summary", settings_view_js)
        self.assertIn("settings-policy-delta-summary", settings_view_js)
        self.assertIn("settings-effective-policy-summary", settings_view_js)
        self.assertIn("settings-save-readiness", settings_view_js)
        self.assertIn("Backend Save remains authoritative", settings_view_js)
        self.assertIn("Local save readiness checklist:", settings_view_js)
        self.assertIn("function settingsSaveReviewRows", settings_view_js)
        self.assertIn("function renderSettingsSaveReviewFromEntries", settings_view_js)
        self.assertIn("Settings Save remains backend-owned", settings_view_js)
        self.assertIn("selectedSettingsSaveReviewKey", settings_view_js)
        self.assertIn("press Save Settings and review the change dialog", settings_view_js)
        self.assertIn("Mutation guardrail: this checklist does not save settings", settings_view_js)
        self.assertIn("parseSettingsPatchJson", settings_view_js)
        self.assertIn("settings-summarize-patch-button", settings_view_js)
        self.assertIn("settings-patch-summary-changed-only", settings_view_js)
        self.assertIn("No changed or unknown keys to show.", settings_view_js)
        self.assertIn("confirm_save", settings_view_js)
        self.assertIn("redacted_diff_lines", settings_view_js)
        self.assertIn("/api/settings/validate", settings_view_js)
        self.assertIn("/api/settings/reload", settings_view_js)
        self.assertIn("/api/settings/preview-patch", settings_view_js)
        self.assertIn("/api/settings/save-patch", settings_view_js)
        self.assertIn("Routing / Size", settings_overview_js)
        self.assertIn("Paths / Safety", settings_overview_js)
        self.assertIn("Subtitles", settings_overview_js)
        self.assertIn("window.mediaPipelineNetworkView", network_view_js)
        self.assertIn("function renderNetworkView", network_view_js)
        self.assertIn("function renderNetworkReadiness", network_view_js)
        self.assertIn("function networkReadinessLines", network_view_js)
        self.assertIn("function networkLifecycleRows", network_view_js)
        self.assertIn("function renderNetworkLifecycleHandoff", network_view_js)
        self.assertIn("Network lifecycle handoff:", network_view_js)
        self.assertIn("Decision rule: trust only backend-owned Network evidence and lifecycle routes", network_view_js)
        self.assertIn("Confirmed lifecycle commands remain confirmation-gated and provider-guarded", network_view_js)
        self.assertIn("function networkEvidenceRows", network_view_js)
        self.assertIn("function renderNetworkEvidenceChecklist", network_view_js)
        self.assertIn("function networkEvidenceSummaryLines", network_view_js)
        self.assertIn("Network evidence checklist:", network_view_js)
        self.assertIn("persisted worker state is visible through /api/network/workers", network_view_js)
        self.assertIn("function renderNetworkWorkerProgress", network_view_js)
        self.assertIn("network-worker-progress-bars", network_view_js)
        self.assertIn("Mutation guardrail: this panel uses backend-owned Network lifecycle routes only", network_view_js)
        self.assertNotIn("function activateNetworkTab", network_view_js)
        self.assertNotIn("mediapipeline-network-tab", network_view_js)
        self.assertIn("function networkRolePanelIds", network_view_js)
        self.assertIn("function syncNetworkRoleDashboards", network_view_js)
        self.assertIn("function networkCoordinatorOverviewModel", network_view_js)
        self.assertIn("function networkWorkerOverviewModel", network_view_js)
        self.assertIn("function renderNetworkRoleDashboards", network_view_js)
        self.assertIn("Remote coordinator queue: Phase 2", network_view_js)
        self.assertIn("unknown/backend evidence missing", network_view_js)
        self.assertIn("function renderNetworkStateFiles", network_view_js)
        self.assertIn("function networkStateFileSummaryLines", network_view_js)
        self.assertIn("Network runtime state file evidence:", network_view_js)
        self.assertIn("Read order: Cluster log -> Coordinator in-flight registry -> Local worker state", network_view_js)
        self.assertIn("network-state-files-rows", network_view_js)
        self.assertIn("live dispatcher lifecycle rows remain backend-owned", network_view_js)
        self.assertIn("This checklist cannot abort, reclaim, release", network_view_js)
        self.assertNotIn("not exposed through the local WebView API yet", network_view_js)
        self.assertIn("function renderNetworkWorkers", network_view_js)
        self.assertIn("function renderNetworkWorkerRows", network_view_js)
        self.assertIn("function networkWorkerRowKey", network_view_js)
        self.assertIn("function filteredNetworkWorkerRows", network_view_js)
        self.assertIn("function initNetworkViewEvents", network_view_js)
        self.assertIn("function renderNetworkWorkerDetail", network_view_js)
        self.assertIn("function renderNetworkOpenHistory", network_view_js)
        self.assertIn("function isNetworkOpenCommand", network_view_js)
        self.assertIn("Backend diagnostics target allowlists remain the source of truth.", network_view_js)
        self.assertIn("Lifecycle controls remain backend-owned", network_view_js)
        self.assertIn("This detail pane is read-only persisted state.", network_view_js)
        self.assertIn("read-only persisted state", network_view_js)
        self.assertIn("Worker board source:", network_view_js)
        self.assertIn("backend Network diagnostics", network_view_js)
        self.assertIn("function renderNetworkSettingsRows", network_view_js)
        self.assertIn("function renderNetworkSettingsPatchHandoff", network_view_js)
        self.assertIn("function previewNetworkSettingsPatch", network_view_js)
        self.assertIn("function saveNetworkSettingsPatch", network_view_js)
        self.assertIn("NetworkRole", network_view_js)
        self.assertIn("WorkerCoordinatorUrl", network_view_js)
        self.assertIn("CoordinatorHeartbeatTimeoutMins", network_view_js)
        self.assertIn("network-readiness-summary", network_view_js)
        self.assertIn("network-settings-rows", network_view_js)
        self.assertIn("network-api-summary", network_view_js)
        self.assertIn("/api/network/workers", js)
        self.assertIn("networkWorkers: values[\"network workers\"]", js)
        self.assertIn("queue: values.queue || {}", js)
        self.assertIn("function createDiagnosticsActiveJobsModule", diagnostics_view_active_jobs_js)
        self.assertIn("window.__diagnosticsActiveJobsModule", diagnostics_view_active_jobs_js)
        self.assertIn("function createDiagnosticsLogModule", diagnostics_view_log_js)
        self.assertIn("window.__diagnosticsLogModule", diagnostics_view_log_js)
        self.assertIn("function createDiagnosticsInvestigationModule", diagnostics_view_investigation_js)
        self.assertIn("window.__diagnosticsInvestigationModule", diagnostics_view_investigation_js)
        self.assertIn("const diagnosticsActiveJobsModule = window.__diagnosticsActiveJobsModule || {}", diagnostics_view_parent_js)
        self.assertIn("const diagnosticsLogModule = window.__diagnosticsLogModule || {}", diagnostics_view_parent_js)
        self.assertIn("const diagnosticsInvestigationModule = window.__diagnosticsInvestigationModule || {}", diagnostics_view_parent_js)
        self.assertIn("delete window.__diagnosticsActiveJobsModule", diagnostics_view_parent_js)
        self.assertIn("delete window.__diagnosticsLogModule", diagnostics_view_parent_js)
        self.assertIn("delete window.__diagnosticsInvestigationModule", diagnostics_view_parent_js)
        self.assertIn("window.mediaPipelineDiagnosticsView", diagnostics_view_js)
        self.assertIn("function renderDiagnostics", diagnostics_view_js)
        self.assertIn("function renderDiagnosticsTriage", diagnostics_view_js)
        self.assertIn("function renderDiagnosticsInvestigationTrail", diagnostics_view_js)
        self.assertIn("function diagnosticsInvestigationTrailLines", diagnostics_view_js)
        self.assertIn("function diagnosticsFirstResponseRows", diagnostics_view_js)
        self.assertIn("function diagnosticsFirstResponseDetailLines", diagnostics_view_js)
        self.assertIn("selectedDiagnosticsFirstResponseKey", diagnostics_view_js)
        self.assertIn("First-response step:", diagnostics_view_js)
        self.assertIn("Mutation guardrail: this detail cannot launch", diagnostics_view_js)
        self.assertIn("function renderDiagnosticsFirstResponse", diagnostics_view_js)
        self.assertIn("function diagnosticsRealMediaBoundaryLines", diagnostics_view_js)
        self.assertIn("function diagnosticsInvestigationActions", diagnostics_view_js)
        self.assertIn("function diagnosticsCrossPageConflictRows", diagnostics_view_js)
        self.assertIn("function diagnosticsConflictSignalLabel", diagnostics_view_js)
        self.assertIn("Diagnostics investigation trail:", diagnostics_view_js)
        self.assertIn("Diagnostics first-response checklist:", diagnostics_view_js)
        self.assertIn("External dependency readiness", diagnostics_view_js)
        self.assertIn("function diagnosticsSamplePolicyReconciliation", diagnostics_view_js)
        self.assertIn("Sample Validation policy reconciliation", diagnostics_view_js)
        self.assertIn("Completed saved-policy reconciliation", diagnostics_view_js)
        self.assertIn("Owner pages: Home owns Preview/Append evidence; Completed owns post-run output proof; Settings owns saved policy.", diagnostics_view_js)
        self.assertIn("Resolve blocked Settings OCR or Maintenance toolchain evidence", diagnostics_view_js)
        self.assertIn("Read order: bounded text first, backend-selected artifact opens next, owning page before any mutation command.", diagnostics_view_js)
        self.assertIn("Mutation guardrail: this checklist cannot launch, drain, save, rename, repair, delete, publish, clear state, or touch files.", diagnostics_view_js)
        self.assertIn("Real-media validation lens:", diagnostics_view_js)
        self.assertIn("Missing diagnostics evidence is not success", diagnostics_view_js)
        self.assertIn("Cross-page row review(s):", diagnostics_view_js)
        self.assertIn("Cross-page conflict handoff(s):", diagnostics_view_js)
        self.assertIn("advisory filename-only", diagnostics_view_js)
        self.assertIn("Mutation guardrail: this trail is read-only", diagnostics_view_js)
        self.assertIn("renderDiagnosticsFirstResponseFn(diagnosticsContext)", js)
        self.assertIn("renderDiagnosticsInvestigationTrail(diagnosticsContext)", js)
        self.assertIn("function renderDiagnosticsDrilldown", diagnostics_view_js)
        self.assertIn("function renderDiagnosticsDrilldownActions", diagnostics_view_js)
        self.assertIn("function renderActiveJobRows", diagnostics_view_js)
        self.assertIn("function renderActiveJobDetail", diagnostics_view_js)
        self.assertIn("function activeJobRowPosture", diagnostics_view_js)
        self.assertIn("function activeJobRowsStatusText", diagnostics_view_js)
        self.assertIn("active/review=", diagnostics_view_js)
        self.assertIn("function diagnosticsActiveJobRealMediaTraceLines", diagnostics_view_js)
        self.assertIn("Real-media sample trace: ActiveJobs", diagnostics_view_js)
        self.assertIn("function activeJobRowKey", diagnostics_view_js)
        self.assertIn("payload.active_job_rows", diagnostics_view_js)
        self.assertIn("function diagnosticsLogRows", diagnostics_view_js)
        self.assertIn("function filteredDiagnosticsLogRows", diagnostics_view_js)
        self.assertIn("function renderDiagnosticsLogRows", diagnostics_view_js)
        self.assertIn("function renderDiagnosticsLogDetail", diagnostics_view_js)
        self.assertIn("function diagnosticsArtifactsForLine", diagnostics_view_js)
        self.assertIn("function diagnosticsLogRowActions", diagnostics_view_js)
        self.assertIn("function diagnosticsLogRowNextStep", diagnostics_view_js)
        self.assertIn("function diagnosticsLogRealMediaTraceLines", diagnostics_view_js)
        self.assertIn("Real-media sample trace: Diagnostics log", diagnostics_view_js)
        self.assertIn("a single log line is not completion, output, sidecar, size, subtitle/audio, or publish proof", diagnostics_view_js)
        self.assertIn("function diagnosticsActionGroups", diagnostics_view_js)
        self.assertIn("function diagnosticsActionPlanLines", diagnostics_view_js)
        self.assertIn("function activeJobDiagnosticsActions", diagnostics_view_js)
        self.assertIn("function renderActiveJobDiagnosticsActions", diagnostics_view_js)
        self.assertIn("function diagnosticsLogGuidanceLines", diagnostics_view_js)
        self.assertIn("Proof boundary: an empty or clean log view", diagnostics_view_js)
        self.assertIn("function renderDiagnosticsLogActions", diagnostics_view_js)
        self.assertIn("function getLastDiagnosticsLogRows", diagnostics_view_js)
        self.assertIn("renderCommandDiagnosticsEvidence(typeof getSelectedCommandEntry", diagnostics_view_js)
        self.assertIn("Diagnostics action plan:", diagnostics_view_js)
        self.assertIn("Read first:", diagnostics_view_js)
        self.assertIn("Open next:", diagnostics_view_js)
        self.assertIn("renderOpenTargetActionGroups?.(container, groups", diagnostics_view_js)
        self.assertIn("append: true", diagnostics_view_js)
        self.assertIn('groupDataset: "diagnosticsActionGroup"', diagnostics_view_js)
        self.assertIn("selected-row actions use backend allowlists", diagnostics_view_js)
        self.assertIn('actionDataset: "diagnosticsLogAction"', diagnostics_view_js)
        self.assertIn('targetDataset: "diagnosticsLogTarget"', diagnostics_view_js)
        self.assertIn("requestDiagnosticsTail(target, button)", diagnostics_view_js)
        self.assertIn("requestDiagnosticsOpen(target, button)", diagnostics_view_js)
        self.assertIn("Fallback for an error line with no specific artifact match.", diagnostics_view_js)
        self.assertIn("Fallback for an active-work line with no specific artifact match.", diagnostics_view_js)
        self.assertIn("Mutation guardrail: log triage is read-only", diagnostics_view_js)
        self.assertIn("window.mediaPipelineDiagnosticsTailView", diagnostics_tail_view_js)
        self.assertIn("function requestDiagnosticsTail", diagnostics_tail_view_js)
        self.assertIn("function renderDiagnosticsTail", diagnostics_tail_view_js)
        self.assertIn("function setDiagnosticsTailTarget", diagnostics_tail_view_js)
        removed_tail_flat_exports = [
            "selectedDiagnosticsTailTarget",
            "selectedDiagnosticsTailMaxBytes",
            "setDiagnosticsTailTarget",
            "setDiagnosticsTailStatus",
            "setDiagnosticsTailBusy",
            "renderDiagnosticsTail",
            "requestDiagnosticsTail",
        ]
        for export_name in removed_tail_flat_exports:
            self.assertNotIn(f"window.{export_name} =", diagnostics_tail_view_js)
        self.assertIn("diagnosticsTailView.requestDiagnosticsTail || window.requestDiagnosticsTail", diagnostics_view_js)
        self.assertIn("function diagnosticsTailEvidence", diagnostics_tail_view_js)
        self.assertIn("function diagnosticsTailEvidenceLines", diagnostics_tail_view_js)
        self.assertIn('Object.assign({ evidence_authority: "backend" }, evidence)', diagnostics_tail_view_js)
        self.assertIn('evidence_authority: "frontend_advisory"', diagnostics_tail_view_js)
        self.assertIn("Tail posture (advisory text scan)", diagnostics_tail_view_js)
        self.assertIn("Evidence authority: ${isFrontendAdvisory ? \"frontend advisory only\" : \"backend\"}", diagnostics_tail_view_js)
        self.assertIn("cannot authorize launch, drain, rename, settings save, lifecycle commands, or file changes", diagnostics_tail_view_js)
        self.assertIn("let diagnosticsTailInFlight = false", diagnostics_tail_view_js)
        self.assertIn("/api/diagnostics/tail", diagnostics_tail_view_js)
        self.assertIn("Backend diagnostics tail uses allowlisted targets only.", diagnostics_tail_view_js)
        self.assertIn("Diagnostics tail evidence is read-only", diagnostics_tail_view_js)
        self.assertIn("window.mediaPipelineDiagnosticsStateSummaryView", diagnostics_state_summary_view_js)
        self.assertIn("function renderDiagnosticsStateSummary", diagnostics_state_summary_view_js)
        self.assertIn("function renderDiagnosticsStateSummaryRows", diagnostics_state_summary_view_js)
        self.assertIn("function renderDiagnosticsStateSummaryDetail", diagnostics_state_summary_view_js)
        self.assertIn("function renderDiagnosticsStateSummaryActions", diagnostics_state_summary_view_js)
        self.assertIn("function renderDiagnosticsStateRecovery", diagnostics_state_summary_view_js)
        self.assertIn("function renderDiagnosticsStateTriage", diagnostics_state_summary_view_js)
        self.assertIn("function renderDiagnosticsStateTriageRows", diagnostics_state_summary_view_js)
        self.assertIn("function renderDiagnosticsStateTriageDetail", diagnostics_state_summary_view_js)
        self.assertIn("function renderDiagnosticsStateTriageActions", diagnostics_state_summary_view_js)
        self.assertIn("function diagnosticsStateTriageRowKey", diagnostics_state_summary_view_js)
        self.assertIn("function diagnosticsStateTriageActionsForItem", diagnostics_state_summary_view_js)
        self.assertIn("function diagnosticsStateArtifactMeaning", diagnostics_state_summary_view_js)
        self.assertIn("function diagnosticsStateRecommendedFirstAction", diagnostics_state_summary_view_js)
        self.assertIn("function diagnosticsStateSummaryRowKey", diagnostics_state_summary_view_js)
        self.assertIn("function diagnosticsStateOperatorStatus", diagnostics_state_summary_view_js)
        self.assertNotIn(
            "window.diagnosticsStateRecommendedFirstAction = diagnosticsStateRecommendedFirstAction",
            diagnostics_state_summary_view_js,
        )
        self.assertNotIn(
            "window.diagnosticsStateOperatorStatus = diagnosticsStateOperatorStatus",
            diagnostics_state_summary_view_js,
        )
        self.assertNotIn(
            "window.diagnosticsStateRowStatusState = diagnosticsStateRowStatusState",
            diagnostics_state_summary_view_js,
        )
        self.assertIn("function diagnosticsStateSettingsToolPathLines", diagnostics_state_summary_view_js)
        self.assertIn("function diagnosticsStateSummaryActionsForItem", diagnostics_state_summary_view_js)
        self.assertIn("function diagnosticsStateArtifactRiskLines", diagnostics_state_summary_view_js)
        self.assertIn("function diagnosticsStateActionPlanLines", diagnostics_state_summary_view_js)
        self.assertIn("Operational interpretation:", diagnostics_state_summary_view_js)
        self.assertIn("renderOpenTargetActionGroups?.(actions, groups", diagnostics_state_summary_view_js)
        self.assertIn('groupDataset: "diagnosticsStateActionGroup"', diagnostics_state_summary_view_js)
        self.assertIn("Process lifecycle evidence", diagnostics_state_summary_view_js)
        self.assertIn("Settings tool-path handoff:", diagnostics_state_summary_view_js)
        self.assertIn("Open Settings > Media Output", diagnostics_state_summary_view_js)
        self.assertIn("Recommended first action:", diagnostics_state_summary_view_js)
        self.assertIn("Recovery stage:", diagnostics_state_summary_view_js)
        self.assertIn("Unsafe if ignored:", diagnostics_state_summary_view_js)
        self.assertIn("Recovery stage and unsafe-if-ignored fields explain", diagnostics_state_summary_view_js)
        self.assertIn("State artifact recovery checklist:", diagnostics_state_summary_view_js)
        self.assertIn("Backend read order:", diagnostics_state_summary_view_js)
        self.assertIn("Backend read-order detail:", diagnostics_state_summary_view_js)
        self.assertIn("Diagnostics artifact JSON", diagnostics_state_summary_view_js)
        self.assertIn("Diagnostics triage JSON", diagnostics_state_summary_view_js)
        self.assertIn("jsonDetailText({", diagnostics_state_summary_view_js)
        self.assertIn('targetDataset: "diagnosticsStateTriageTarget"', diagnostics_state_summary_view_js)
        self.assertIn("Close Readiness is the authority", diagnostics_state_summary_view_js)
        self.assertIn("window.requestDiagnosticsOpen(target, button)", diagnostics_state_summary_view_js)
        self.assertIn("window.requestDiagnosticsTail(target, button)", diagnostics_state_summary_view_js)
        self.assertIn("Mutation guardrail: this checklist does not repair", diagnostics_state_summary_view_js)
        self.assertIn("Guardrail: this view is read-only", diagnostics_state_summary_view_js)
        self.assertIn('id="active-job-diagnostics-actions"', html)
        self.assertIn("mediaPipelineDiagnosticsTailView", diagnostics_view_js)
        self.assertIn("function initDiagnosticsViewEvents", diagnostics_view_js)
        self.assertIn("No diagnostics log rows match the current filter.", diagnostics_view_js)
        self.assertIn("selected-row actions use backend allowlists", diagnostics_view_js)
        self.assertIn("function diagnosticsSeverityForLine", diagnostics_view_js)
        self.assertIn("function diagnosticsMalformedStateLines", diagnostics_view_js)
        self.assertIn("function diagnosticsArtifactMatches", diagnostics_view_js)
        self.assertIn("diagnosticsArtifactTargets", diagnostics_view_js)
        self.assertIn("button.dataset.openDiagnostics = openTarget", diagnostics_view_js)
        self.assertIn("requestDiagnosticsOpen(openTarget, button)", diagnostics_view_js)
        self.assertIn("tailButton.dataset.readDiagnosticsTail = artifact.tailTarget", diagnostics_view_js)
        self.assertIn("requestDiagnosticsTail(artifact.tailTarget, tailButton)", diagnostics_view_js)
        self.assertIn('tailTarget: "last_stderr_log"', diagnostics_view_js)
        self.assertIn('tailTarget: "queue_snapshot"', diagnostics_view_js)
        self.assertIn('tailTarget: "latest_failure_report"', diagnostics_view_js)
        self.assertIn('tailTarget: "cluster_log"', diagnostics_view_js)
        self.assertIn("BDPGS OCR settings evidence", diagnostics_view_js)
        self.assertIn("settings_bdpgs_ocr_paths", diagnostics_view_js)
        self.assertIn("VobSub OCR settings evidence", diagnostics_view_js)
        self.assertIn("settings_vobsub_ocr_paths", diagnostics_view_js)
        self.assertIn("Diagnostics does not edit settings or run OCR.", diagnostics_view_js)
        self.assertIn("orphan payload", diagnostics_view_js)
        self.assertIn("malformed manifests", diagnostics_view_js)
        self.assertIn("Malformed/stale runtime-state hint(s):", diagnostics_view_js)
        self.assertIn("Severity groups:", diagnostics_view_js)
        self.assertIn("Check Close Readiness first", diagnostics_view_js)
        self.assertIn("diagnostics-first-response-status", html)
        self.assertIn("diagnostics-first-response-summary", html)
        self.assertIn("diagnostics-first-response-rows", html)
        self.assertIn("diagnostics-first-response-detail", html)
        self.assertIn("Artifact drilldown is read-only", diagnostics_view_js)
        self.assertIn("Open and Read buttons below use backend allowlists", diagnostics_view_js)
        self.assertIn("backend allowlist", diagnostics_view_js)
        self.assertIn("function requestDiagnosticsOpen", diagnostics_view_js)
        self.assertIn("function setDiagnosticsOpenStatus", diagnostics_view_js)
        self.assertIn("home-runtime-open-status", diagnostics_view_js)
        self.assertIn("function renderDiagnosticsOpenHistory", diagnostics_view_js)
        self.assertIn("function isDiagnosticsOpenCommand", diagnostics_view_js)
        self.assertIn("Backend diagnostics target allowlists remain the source of truth.", diagnostics_view_js)
        self.assertIn("let diagnosticsOpenInFlight = false", diagnostics_view_js)
        self.assertIn("function setDiagnosticsOpenBusy", diagnostics_view_js)
        self.assertIn("function rejectDiagnosticsOpenWhileBusy", diagnostics_view_js)
        self.assertIn("Another diagnostics open command is already in progress.", diagnostics_view_js)
        self.assertIn("log_tail", diagnostics_view_js)
        self.assertIn("/api/diagnostics/open", diagnostics_view_js)
        self.assertIn("/api/diagnostics/tdarr-matrix-audit", diagnostics_view_js)
        self.assertIn("data-tdarr-matrix-audit-action", html)
        self.assertIn("window.mediaPipelineReportsView", reports_view_js)
        self.assertIn("function renderReports", reports_view_js)
        self.assertIn("mediaPipelineProgressView?.renderAuditProgressInto", reports_view_js)
        self.assertIn("report-progress-bars", reports_view_js)
        self.assertIn("function renderReportTriage", reports_view_js)
        self.assertIn("function renderReportInvestigation", reports_view_js)
        self.assertIn("function reportInvestigationChecklistLines", reports_view_js)
        self.assertIn("Reports investigation checklist:", reports_view_js)
        self.assertIn("function initReportsViewEvents", reports_view_js)
        self.assertNotIn("window.initReportsViewEvents = initReportsViewEvents", reports_view_js)
        self.assertNotIn("window.renderFailureRows = renderFailureRows", reports_view_js)
        self.assertNotIn("window.renderAuditRows = renderAuditRows", reports_view_js)
        self.assertNotIn("window.renderAuditControls = renderAuditControls", reports_view_js)
        self.assertNotIn("window.renderReportOpenHistory = renderReportOpenHistory", reports_view_js)
        self.assertNotIn("function renderReportLaunchHandoff", reports_view_js)
        self.assertNotIn("function reportLaunchHandoffLines", reports_view_js)
        self.assertNotIn("function reportGoToCsvRerun", reports_view_js)
        self.assertNotIn("function reportGoToAuditLaunch", reports_view_js)
        self.assertNotIn("function reportGoToDiagnostics", reports_view_js)
        self.assertNotIn("Reports to Launch handoff:", reports_view_js)
        self.assertNotIn("Paste the verified CSV path manually", reports_view_js)
        self.assertNotIn("It never fills CSV Path, starts CSV Rerun, runs Audit", reports_view_js)
        self.assertNotIn("activateLaunchTab", reports_view_js)
        self.assertNotIn("renderLaunchAuditProgress(lastReportSnapshot)", reports_view_js)
        self.assertIn("function reportTriageStatus", reports_view_js)
        self.assertIn("function reportTriageLines", reports_view_js)
        self.assertIn("Mutation guardrail: rerun/export/repair actions must remain backend-owned commands", reports_view_js)
        self.assertIn("function renderFailurePreview", reports_view_js)
        self.assertIn("function renderFailureRows", reports_view_js)
        self.assertIn("function selectFailureRow", reports_view_js)
        self.assertIn("function failureRetryStatePayload", reports_view_js)
        self.assertIn("desktop_retry_state.v1", reports_view_js)
        self.assertIn("Retry route/command:", reports_view_js)
        self.assertIn("function toggleFailureRowSelection", reports_view_js)
        self.assertIn("function allFailureMarkerPaths", reports_view_js)
        self.assertIn("function failureRecordedText", reports_view_js)
        self.assertIn("function renderFailureDetail", reports_view_js)
        self.assertIn("function renderFailureReviewBoard", reports_view_js)
        self.assertIn("function failureReviewBoardLines", reports_view_js)
        self.assertIn("function failureReviewBoardTiles", reports_view_js)
        self.assertIn("review-tile", reports_view_js)
        self.assertIn("Failure review board:", reports_view_js)
        self.assertIn("function failureEmptyStateMessage", reports_view_js)
        self.assertIn("No failure rows found for the selected source.", reports_view_js)
        self.assertIn("Select a row or use Open details", reports_view_js)
        self.assertIn("source_json", reports_view_js)
        self.assertIn("function requestFailureMarkerClear", reports_view_js)
        self.assertIn("function requestFailureRowClear", reports_view_js)
        self.assertIn("function initReportsTabNav", reports_view_js)
        self.assertIn("function activateReportsTab", reports_view_js)
        self.assertIn('/api/failures/clear', reports_view_js)
        self.assertIn("confirm_clear: !dryRun", reports_view_js)
        self.assertIn("Select one or more failure marker rows first.", reports_view_js)
        self.assertIn("It does not delete media files, logs, reports, manifests, source files, or output files", reports_view_js)
        self.assertIn("function renderAuditPreview", reports_view_js)
        self.assertIn("function renderAuditControls", reports_view_js)
        self.assertIn("function renderAuditRows", reports_view_js)
        self.assertIn("function selectAuditRow", reports_view_js)
        self.assertIn("function toggleAuditRowSelection", reports_view_js)
        self.assertIn("function selectedAuditRowKeysList", reports_view_js)
        self.assertIn('apiPost("/api/audit/score-policy", request)', reports_view_js)
        self.assertIn("policy.issue_code_weights = {};", reports_view_js)
        self.assertIn("renderReportAuditIssueRows", reports_view_js)
        self.assertIn('apiPost("/api/audit/ignore", request)', reports_view_js)
        self.assertIn('apiPost("/api/audit/export-rerun-csv", request)', reports_view_js)
        self.assertIn("function renderAuditDetail", reports_view_js)
        self.assertIn("function renderAuditReviewBoard", reports_view_js)
        self.assertIn("function auditReviewBoardLines", reports_view_js)
        self.assertIn("Audit review board:", reports_view_js)
        self.assertIn("function auditEmptyStateMessage", reports_view_js)
        self.assertIn("No audit rows found.", reports_view_js)
        self.assertIn("Select a row to inspect priority score", reports_view_js)
        self.assertIn("latest_paths", reports_view_js)
        self.assertIn("priority_score", reports_view_js)
        self.assertIn("function reportOpenTarget", reports_view_js)
        self.assertIn("function isReportOpenCommand", reports_view_js)
        self.assertIn("function renderReportOpenHistory", reports_view_js)
        self.assertIn("Backend diagnostics target allowlists remain the source of truth.", reports_view_js)
        self.assertIn("requestDiagnosticsOpen(target, button)", reports_view_js)
        self.assertIn("latest_failure_report", reports_view_js)
        self.assertIn("latest_audit_csv", reports_view_js)
        self.assertIn("pending_publish", reports_view_js)
        self.assertIn("Reports triage is read-only; CSV rerun/export decisions must stay backend-owned.", reports_view_js)
        self.assertIn('<th scope="col">Action</th>', html)
        self.assertIn("window.mediaPipelineScheduleView", schedule_view_js)
        self.assertIn("function renderSchedule", schedule_view_js)
        self.assertIn("function scheduleDisplayValue", schedule_view_js)
        self.assertIn("function scheduleLaunchGuidanceLines", schedule_view_js)
        self.assertIn("function renderScheduleGuidance", schedule_view_js)
        self.assertIn("function renderScheduleTimingTrust", schedule_view_js)
        self.assertIn("function scheduleTimingTrustLines", schedule_view_js)
        self.assertIn("function renderScheduleCoverage", schedule_view_js)
        self.assertIn("function scheduleCoverageRows", schedule_view_js)
        self.assertIn("function scheduleCoverageDetailLines", schedule_view_js)
        self.assertIn("function scheduleWatcherSummary", schedule_view_js)
        self.assertIn("Generation:", schedule_view_js)
        self.assertIn("Continuous watcher", schedule_view_js)
        self.assertIn("Backend continuous watcher:", schedule_view_js)
        self.assertIn("function scheduleDayDetailLines", schedule_view_js)
        self.assertIn("function renderScheduleEditor", schedule_view_js)
        self.assertIn("function initScheduleViewEvents", schedule_view_js)
        self.assertIn("function previewScheduleEditor", schedule_view_js)
        self.assertIn("function saveScheduleEditor", schedule_view_js)
        self.assertIn("function scheduleEditorRequest", schedule_view_js)
        self.assertIn("function scheduleSetDayBlocks", schedule_view_js)
        self.assertIn("function scheduleBlockLabel", schedule_view_js)
        self.assertIn("function loadCurrentScheduleIntoEditor", schedule_view_js)
        for flat_schedule_export in (
            "window.renderSchedule =",
            "window.renderScheduleTimingTrust =",
            "window.initScheduleViewEvents =",
            "window.scheduleTimingTrustStatus =",
            "window.scheduleTimingTrustLines =",
            "window.scheduleCurrentLaunchSelection =",
            "window.scheduleWatcherSummary =",
            "window.schedulePipelineModeLabel =",
            "window.scheduleOverrideLabel =",
            "window.scheduleDisplayValue =",
        ):
            self.assertNotIn(flat_schedule_export, schedule_view_js)
        self.assertIn("function clearScheduleEditorWeek", schedule_view_js)
        self.assertIn("function allowAllScheduleEditorWeek", schedule_view_js)
        self.assertNotIn("function scheduleCopyEditorDayToTargets", schedule_view_js)
        self.assertIn("schedule-coverage-rows", html)
        self.assertIn("schedule-coverage-detail", html)
        self.assertIn("schedule-day-detail", html)
        self.assertIn("schedule-editor-rows", html)
        self.assertIn("30-Minute Blocks", html)
        self.assertIn("Edit Schedule", html)
        self.assertNotIn("data-schedule-copy-source", html)
        self.assertNotIn("data-schedule-copy-target", html)
        self.assertNotIn("data-schedule-copy-apply", html)
        self.assertIn("/api/schedule/preview", schedule_view_js)
        self.assertIn("/api/schedule/save", schedule_view_js)
        self.assertIn("Writes app state", schedule_view_js)
        self.assertIn("Coverage Review", html)
        self.assertIn("Schedule timing trust:", schedule_view_js)
        self.assertIn("Mutation guardrail: this trust panel is read-only", schedule_view_js)
        self.assertIn("Mutation guardrail: WebView Schedule can preview and save", schedule_view_js)
        self.assertIn("Backend launch gating remains the source of truth.", schedule_view_js)
        self.assertIn("schedule-stop watcher", schedule_view_js)
        self.assertIn("schedule-day-rows", schedule_view_js)
        self.assertIn("window.mediaPipelineMaintenanceView", maintenance_view_js)
        self.assertIn("function renderMaintenance", maintenance_view_js)
        self.assertIn("function renderMaintenanceRows", maintenance_view_js)
        self.assertIn("function renderMaintenanceDetail", maintenance_view_js)
        self.assertIn("function renderMaintenanceHealthProgress", maintenance_view_js)
        self.assertIn("function pollMaintenanceProgress", maintenance_view_js)
        self.assertIn("/api/maintenance/progress", maintenance_view_js)
        self.assertIn("function maintenanceDiagnosticsActionsForRow", maintenance_view_js)
        self.assertIn("function renderMaintenanceDiagnosticsActions", maintenance_view_js)
        self.assertIn("function renderMaintenanceReadiness", maintenance_view_js)
        self.assertIn("function renderMaintenanceToolchain", maintenance_view_js)
        self.assertIn("function renderMaintenanceReadinessError", maintenance_view_js)
        self.assertIn("function maintenanceReadinessStatus", maintenance_view_js)
        self.assertIn("function maintenanceToolchainStatus", maintenance_view_js)
        self.assertIn("function maintenanceToolchainLines", maintenance_view_js)
        self.assertIn("function maintenanceReadinessLines", maintenance_view_js)
        self.assertIn("function maintenanceRealMediaBoundaryLines", maintenance_view_js)
        self.assertIn("function renderMaintenanceDryRunConfidence", maintenance_view_js)
        self.assertIn("function maintenanceDryRunConfidenceLines", maintenance_view_js)
        self.assertIn("function maintenanceReleaseOptionReviewLines", maintenance_view_js)
        self.assertIn("function initMaintenanceViewEvents", maintenance_view_js)
        self.assertIn("Real-media validation boundary:", maintenance_view_js)
        self.assertIn("Toolchain readiness:", maintenance_view_js)
        self.assertIn("WebView does not resolve arbitrary tools", maintenance_view_js)
        self.assertIn("Tool kind:", maintenance_view_js)
        self.assertIn("Failure scope:", maintenance_view_js)
        self.assertIn("Maintenance health and dry-run commands prove packaging/backfill environment posture only.", maintenance_view_js)
        self.assertIn("release dry-run output does not validate FFmpeg", maintenance_view_js)
        self.assertIn("completed-manifest backfill dry-run output does not prove media processing", maintenance_view_js)
        self.assertIn("Maintenance dry-run confidence:", maintenance_view_js)
        self.assertIn("Deployment option review:", maintenance_view_js)
        self.assertIn("Preview only; no release folder, manifest, or zip was written.", maintenance_view_js)
        self.assertIn("preview reports the zip plan, Create writes it", maintenance_view_js)
        self.assertIn("Create Deployment may write a release folder/manifest/zip", maintenance_view_js)
        self.assertIn("Backfill remains dry-run", maintenance_view_js)
        self.assertIn("diagnosticsBridgeRowTrustLines", maintenance_view_js)
        self.assertIn("Dry-run trust summary:", maintenance_view_js)
        self.assertIn("must remain a backend dry-run command", maintenance_view_js)
        self.assertIn("makeRowSelectable", maintenance_view_js)
        self.assertIn("updateTableStatusLegend", maintenance_view_js)
        self.assertIn("appendDiagnosticsBridgeGroupedButtons", maintenance_view_js)
        self.assertIn("function refreshMaintenance", maintenance_view_js)
        self.assertIn("let maintenanceRefreshInFlight = false", maintenance_view_js)
        self.assertIn("maintenanceRefreshQueued = true", maintenance_view_js)
        self.assertIn("window.setTimeout(refreshMaintenance, 0)", maintenance_view_js)
        self.assertIn("const maintenanceDryRunButtonIds", maintenance_view_js)
        self.assertIn("function setMaintenanceDryRunBusy", maintenance_view_js)
        self.assertIn("function rejectMaintenanceDryRunWhileBusy", maintenance_view_js)
        self.assertIn("function collectReleaseDryRunRequest", maintenance_view_js)
        self.assertIn("function collectReleaseBuildRequest", maintenance_view_js)
        self.assertIn("function runReleaseDryRun", maintenance_view_js)
        self.assertIn("function runReleaseBuild", maintenance_view_js)
        removed_maintenance_flat_exports = [
            "hasMaintenanceLoaded",
            "getLastMaintenance",
            "refreshMaintenance",
            "initMaintenanceViewEvents",
            "runReleaseDryRun",
            "runReleaseBuild",
            "runBackfillDryRun",
        ]
        for export_name in removed_maintenance_flat_exports:
            self.assertNotIn(f"window.{export_name} =", maintenance_view_js)
        self.assertIn("function renderReleaseBuildResult", maintenance_view_js)
        self.assertIn("function renderReleasePackageProgress", maintenance_view_js)
        self.assertIn("function renderReleasePackageInFlightProgress", maintenance_view_js)
        self.assertIn("function setReleasePackageStatus", maintenance_view_js)
        self.assertIn("function releasePackageResultStatus", maintenance_view_js)
        self.assertIn("function releasePackageProgressBars", maintenance_view_js)
        self.assertIn('targetId = "release-dry-run-progress-bars"', maintenance_view_js)
        self.assertIn("renderProgressBarsInto(targetId", maintenance_view_js)
        self.assertIn('renderReleasePackageProgress(result, "release-build-progress-bars")', maintenance_view_js)
        self.assertIn('"Planning"', maintenance_view_js)
        self.assertIn('"Building"', maintenance_view_js)
        self.assertIn('"Build done"', maintenance_view_js)
        self.assertIn("function runBackfillDryRun", maintenance_view_js)
        self.assertIn("function renderBackfillProgress", maintenance_view_js)
        self.assertIn("function backfillProgressBars", maintenance_view_js)
        self.assertIn('renderProgressBarsInto("backfill-dry-run-progress-bars"', maintenance_view_js)
        self.assertIn("function runDependencyAtlas", maintenance_view_js)
        self.assertIn("function renderDependencyAtlasResult", maintenance_view_js)
        self.assertIn("function renderDependencyAtlasProgress", maintenance_view_js)
        self.assertIn("function dependencyAtlasProgressBars", maintenance_view_js)
        self.assertIn("function openDependencyAtlasFolder", maintenance_view_js)
        self.assertIn('renderProgressBarsInto("dependency-atlas-progress-bars"', maintenance_view_js)
        self.assertIn("function isMaintenanceDryRunCommand", maintenance_view_js)
        self.assertIn("function renderMaintenanceDryRunHistory", maintenance_view_js)
        self.assertIn("maintenance-dry-run-history", maintenance_view_js)
        self.assertIn("/api/maintenance", maintenance_view_js)
        self.assertIn("/api/maintenance/release-dry-run", maintenance_view_js)
        self.assertIn("/api/maintenance/release-build", maintenance_view_js)
        self.assertIn("/api/maintenance/dependency-atlas", maintenance_view_js)
        self.assertIn("/api/maintenance/dependency-atlas/open-folder", maintenance_view_js)
        self.assertIn('command: "maintenance.release_dry_run"', maintenance_view_js)
        self.assertIn('command: "maintenance.release_build"', maintenance_view_js)
        self.assertIn('command: "maintenance.completed_backfill_dry_run"', maintenance_view_js)
        self.assertIn('command: "maintenance.dependency_atlas"', maintenance_view_js)
        self.assertIn('command: "maintenance.dependency_atlas_open_folder"', maintenance_view_js)
        self.assertIn("window.mediaPipelineTelemetryView", telemetry_view_js)
        self.assertIn("const formatters = window.mediaPipelineFormatters || {}", telemetry_view_js)
        self.assertIn("const formatPercent = typeof formatters.formatPercent", telemetry_view_js)
        self.assertIn("const formatMemoryMb = typeof formatters.formatMemoryMb", telemetry_view_js)
        self.assertIn("function renderTelemetry", telemetry_view_js)
        self.assertIn("function renderGpuRows", telemetry_view_js)
        self.assertIn("function drawTelemetryChart", telemetry_view_js)
        self.assertIn("function formatGpuEncoderPercent", telemetry_view_js)
        self.assertIn("function telemetryGpuNote", telemetry_view_js)
        self.assertIn("function renderTelemetryReadiness", telemetry_view_js)
        self.assertIn("function telemetryReadinessStatus", telemetry_view_js)
        self.assertIn("function telemetryReadinessLines", telemetry_view_js)
        self.assertIn("function telemetryGpuUsagePayload", telemetry_view_js)
        self.assertIn("desktop_gpu_encoder_usage.v1", telemetry_view_js)
        self.assertIn("Encoder sessions", telemetry_view_js)
        self.assertIn("GPU video encoder telemetry available.", telemetry_view_js)
        self.assertIn("Monitoring normal", telemetry_view_js)
        self.assertIn("Telemetry sample is stale.", telemetry_view_js)
        self.assertIn("function telemetryOperatingState", telemetry_view_js)
        self.assertIn("function telemetryChartMetaText", telemetry_view_js)
        self.assertNotIn("0% idle", telemetry_view_js)
        self.assertIn("NVENC idle as expected", telemetry_view_js)
        self.assertIn("waiting for sample", telemetry_view_js)
        self.assertIn("GPU telemetry source returned no per-device rows.", telemetry_view_js)
        self.assertIn("window.mediaPipelineProgressView", progress_view_js)
        self.assertIn("function renderProgressBars", progress_view_js)
        self.assertIn("function renderAuditProgressInto", progress_view_js)
        self.assertIn("function auditProgressBars", progress_view_js)
        self.assertIn("progress-bar-list", progress_view_js)
        self.assertIn("diagnostics-progress-bars", progress_view_js)
        self.assertIn("report_step_total", progress_view_js)
        self.assertIn("role\", \"progressbar", progress_view_js)
        self.assertIn("function renderProgressDetails", progress_view_js)
        self.assertIn("function renderProgressEvidence", progress_view_js)
        for flat_progress_export in (
            "window.renderProgressBarsInto =",
            "window.renderProgressBars =",
            "window.renderProgressDetails =",
            "window.renderProgressEvidence =",
        ):
            self.assertNotIn(flat_progress_export, progress_view_js)
        self.assertIn("function progressEvidenceRows", progress_view_js)
        self.assertIn("function progressFfmpegPayload", progress_view_js)
        self.assertIn("desktop_ffmpeg_progress.v1", progress_view_js)
        self.assertIn("FFmpeg progress proof", progress_view_js)
        self.assertIn("function progressEtaPayload", progress_view_js)
        self.assertIn("desktop_eta.v1", progress_view_js)
        self.assertIn("ETA", progress_view_js)
        self.assertIn("Progress evidence board:", progress_view_js)
        self.assertIn("Progress explains current activity; it is not publish, completion, or output-integrity proof.", progress_view_js)
        self.assertIn("Mutation guardrail: this board is read-only", progress_view_js)
        self.assertIn("function renderDiagnosticsProgress", progress_view_js)
        self.assertIn("function diagnosticsProgressRows", progress_view_js)
        self.assertIn("progressFfmpegSummaryLine", progress_view_js)
        self.assertIn("Stale progress warning:", progress_view_js)
        self.assertIn("Runtime progress looks older than the current backend state", progress_view_js)
        self.assertIn("Stale progress review", progress_view_js)
        self.assertIn("Mutation guardrail: this table is read-only", progress_view_js)
        self.assertIn("function renderPipelineEvents", progress_view_js)
        self.assertIn("function renderHomeActiveWork", progress_view_js)
        self.assertNotIn("window.renderAuditProgressInto = renderAuditProgressInto", progress_view_js)
        self.assertNotIn("window.renderPipelineEvents = renderPipelineEvents", progress_view_js)
        self.assertNotIn("window.renderHomeActiveWork = renderHomeActiveWork", progress_view_js)
        self.assertNotIn("window.renderLiveRunStrip = renderLiveRunStrip", progress_view_js)
        self.assertIn("function activeWorkNextStep", progress_view_js)
        self.assertIn("CurrentStagePercent", progress_view_js)
        self.assertIn("ActiveJobs:", progress_view_js)
        self.assertIn("Inspect Progress Details, Diagnostics > ActiveJobs, and Run Logs", progress_view_js)
        self.assertIn("No pipeline events loaded.", progress_view_js)
        self.assertIn("window.mediaPipelineLaunchReadinessView", launch_readiness_view_js)
        self.assertIn("function launchReadinessSettingsStatus", launch_readiness_view_js)
        self.assertIn("function launchReadinessStatus", launch_readiness_view_js)
        self.assertIn("function launchReadinessLines", launch_readiness_view_js)
        self.assertIn("function launchReadinessScheduleWatcherSummary", launch_readiness_view_js)
        self.assertIn("function launchReadinessBackendReadiness", launch_readiness_view_js)
        self.assertIn("function launchReadinessBackendLines", launch_readiness_view_js)
        self.assertIn("Launch readiness (backend-authored):", launch_readiness_view_js)
        self.assertIn("Evidence authority: frontend advisory only until backend preflight payload is loaded.", launch_readiness_view_js)
        self.assertIn("function launchTimingTrustLines", launch_readiness_view_js)
        self.assertIn("function renderLaunchTimingTrust", launch_readiness_view_js)
        self.assertIn("function getLastLaunchReadinessPayload", launch_readiness_view_js)
        self.assertIn("renderLaunchSettingsIntentChecklist(undefined, lastLaunchReadinessPayload)", launch_readiness_view_js)
        self.assertIn("Launch timing trust:", launch_readiness_view_js)
        self.assertIn("Mutation guardrail: this Launch timing panel is read-only", launch_readiness_view_js)
        self.assertIn("function renderLaunchReadiness", launch_readiness_view_js)
        self.assertIn("Saved settings:", launch_readiness_view_js)
        self.assertIn("Settings issue", launch_readiness_view_js)
        self.assertIn("Saved settings need review", launch_readiness_view_js)
        self.assertIn("Active work is reported", launch_readiness_view_js)
        self.assertIn("Backend launch locking and gating remain the source of truth.", launch_readiness_view_js)
        self.assertIn("Run Once and Continuous are schedule-blocked", launch_readiness_view_js)
        self.assertIn("Backend continuous watcher:", launch_readiness_view_js)
        self.assertNotIn("window.launchReadinessStatus =", launch_readiness_view_js)
        self.assertNotIn("window.launchReadinessStatusState =", launch_readiness_view_js)
        self.assertNotIn("window.launchReadinessLines =", launch_readiness_view_js)
        self.assertNotIn("window.launchReadinessRecoveryActions =", launch_readiness_view_js)
        self.assertNotIn("window.renderLaunchReadinessRecoveryActions =", launch_readiness_view_js)
        self.assertNotIn("window.launchTimingStatus =", launch_readiness_view_js)
        self.assertNotIn("window.launchTimingTrustLines =", launch_readiness_view_js)
        self.assertNotIn("window.renderLaunchTimingTrust =", launch_readiness_view_js)
        self.assertNotIn("window.renderLaunchReadiness =", launch_readiness_view_js)
        self.assertNotIn("window.getLastLaunchReadinessPayload =", launch_readiness_view_js)
        self.assertIn("window.mediaPipelineLaunchHistoryView", launch_history_view_js)
        self.assertIn("function isLaunchCommand", launch_history_view_js)
        self.assertIn("function renderLaunchCommandHistory", launch_history_view_js)
        self.assertIn("function launchHistoryLine", launch_history_view_js)
        self.assertIn("function launchHistoryTarget", launch_history_view_js)
        self.assertIn("function launchHistoryRequest", launch_history_view_js)
        self.assertIn("function launchCommandCorrelationRows", launch_history_view_js)
        self.assertIn("function launchCommandCorrelationStatus", launch_history_view_js)
        self.assertIn("function launchCommandCorrelationSummary", launch_history_view_js)
        self.assertIn("function launchCommandDiagnosticsActions", launch_history_view_js)
        self.assertIn("function launchCommandDiagnosticsGuidanceLines", launch_history_view_js)
        self.assertIn("function renderLaunchCommandDiagnosticsActions", launch_history_view_js)
        self.assertIn("function launchCommandReviewRows", launch_history_view_js)
        self.assertIn("function launchCommandReviewDetailLines", launch_history_view_js)
        self.assertIn("function renderLaunchCommandReview", launch_history_view_js)
        self.assertIn("Launch command review:", launch_history_view_js)
        self.assertIn("Checklist correlation:", launch_history_view_js)
        self.assertIn("Correlated checklist/preflight context:", launch_history_view_js)
        self.assertIn("Predicted by checklist", launch_history_view_js)
        self.assertIn("Not predicted by cached checks", launch_history_view_js)
        self.assertIn("Launch diagnostics retry guidance:", launch_history_view_js)
        self.assertIn("Retry rule: do not press Start again until command detail, correlated checklist context, and diagnostics targets agree on the cause.", launch_history_view_js)
        self.assertIn("these actions use backend allowlisted diagnostics targets only", launch_history_view_js)
        self.assertIn("launchCommandDiagnosticsAdd(actions, \"open\", \"queue_snapshot\"", launch_history_view_js)
        self.assertIn("launchCommandDiagnosticsAdd(actions, \"open\", \"active_jobs\"", launch_history_view_js)
        self.assertIn("launchCommandDiagnosticsAdd(actions, \"tail\", \"latest_failure_report\"", launch_history_view_js)
        self.assertIn("requestCommandDiagnosticsAction(action)", launch_history_view_js)
        self.assertIn("function launchViewApi", launch_history_view_js)
        self.assertIn("launchView.launchBackendPreflightPayloadForTarget(target)", launch_history_view_js)
        self.assertIn("queueLaunchDecisionRows(undefined, undefined, history)", launch_history_view_js)
        self.assertIn("launchSettingsIntentRows(request)", launch_history_view_js)
        self.assertIn("selecting a launch command review row selects that command", launch_history_view_js)
        self.assertIn("launch, CSV rerun, drain, and control commands remain backend-owned", launch_history_view_js)
        self.assertIn("Pending publish drain history remains on the Pending Publish page.", launch_history_view_js)
        self.assertIn("renderCompactCommandHistoryBlock({", launch_history_view_js)
        self.assertIn("Backend launch locking and validation remain the source of truth.", launch_history_view_js)
        self.assertNotIn("window.launchCommandCorrelationRows =", launch_history_view_js)
        self.assertNotIn("window.launchCommandCorrelationStatus =", launch_history_view_js)
        self.assertNotIn("window.launchCommandDiagnosticsActions =", launch_history_view_js)
        self.assertNotIn("window.launchCommandReviewRows =", launch_history_view_js)
        self.assertNotIn("window.launchCommandReviewStatus =", launch_history_view_js)
        self.assertNotIn("window.launchCommandReviewSummaryLines =", launch_history_view_js)
        self.assertNotIn("window.renderLaunchCommandHistory =", launch_history_view_js)
        self.assertNotIn("window.isLaunchCommand =", launch_history_view_js)
        self.assertNotIn("window.launchHistoryLine =", launch_history_view_js)
        self.assertIn("window.mediaPipelineLaunchView", launch_view_js)
        self.assertIn("function requestPipelineControl", launch_view_js)
        self.assertIn("function confirmControlAction", launch_view_js)
        self.assertIn("let controlCommandInFlight = false", launch_view_js)
        self.assertIn("function setControlCommandBusy", launch_view_js)
        self.assertIn("function rejectControlCommandWhileBusy", launch_view_js)
        self.assertIn("Another pipeline control command is already in progress.", launch_view_js)
        self.assertIn("function renderPipelineControlHistory", launch_view_preflight_js)
        self.assertIn("function isPipelineControlCommand", launch_view_preflight_js)
        self.assertIn("Backend control-flag writes and launch locks remain the source of truth.", launch_view_preflight_js)
        self.assertIn("mediaPipelineLaunchReadinessView", launch_view_js)
        self.assertIn("mediaPipelineLaunchHistoryView", launch_view_js)
        self.assertIn("const launchReadinessStatus = launchReadinessView.launchReadinessStatus || window.launchReadinessStatus", launch_view_js)
        self.assertIn("const launchTimingStatus = launchReadinessView.launchTimingStatus || window.launchTimingStatus", launch_view_js)
        self.assertIn("const getLastLaunchReadinessPayload = launchReadinessView.getLastLaunchReadinessPayload || window.getLastLaunchReadinessPayload", launch_view_js)
        self.assertNotIn("window.launchReadinessStatus =", launch_view_js)
        self.assertNotIn("window.launchReadinessLines =", launch_view_js)
        self.assertNotIn("window.renderLaunchReadiness =", launch_view_js)
        self.assertIn("const isLaunchCommand = launchHistoryView.isLaunchCommand || window.isLaunchCommand", launch_view_js)
        self.assertIn("const launchCommandCorrelationRows = launchHistoryView.launchCommandCorrelationRows", launch_view_js)
        self.assertIn("launchCommandReviewRows: typeof launchCommandReviewRows === \"function\" ? launchCommandReviewRows : null", launch_view_js)
        self.assertIn("function createLaunchControllerStateModule", launch_view_js)
        self.assertIn("window.__launchControllerStateModule", launch_view_js)
        self.assertIn("const launchControllerStateModule = window.__launchControllerStateModule || {}", launch_view_js)
        self.assertIn("delete window.__launchControllerStateModule", launch_view_js)
        self.assertIn("function createLaunchStatusRenderModule", launch_view_js)
        self.assertIn("window.__launchStatusRenderModule", launch_view_js)
        self.assertIn("const launchStatusRenderModule = window.__launchStatusRenderModule || {}", launch_view_js)
        self.assertIn("delete window.__launchStatusRenderModule", launch_view_js)
        self.assertIn("function createLaunchStartRequestModule", launch_view_js)
        self.assertIn("window.__launchStartRequestModule", launch_view_js)
        self.assertIn("const launchStartRequestModule = window.__launchStartRequestModule || {}", launch_view_js)
        self.assertIn("delete window.__launchStartRequestModule", launch_view_js)
        self.assertIn("function createLaunchScopeControlsModule", launch_view_js)
        self.assertIn("window.__launchScopeControlsModule", launch_view_js)
        self.assertIn("const launchScopeControlsModule = window.__launchScopeControlsModule || {}", launch_view_js)
        self.assertIn("delete window.__launchScopeControlsModule", launch_view_js)
        self.assertIn("function createLaunchCommandButtonsModule", launch_view_js)
        self.assertIn("window.__launchCommandButtonsModule", launch_view_js)
        self.assertIn("const launchCommandButtonsModule = window.__launchCommandButtonsModule || {}", launch_view_js)
        self.assertIn("delete window.__launchCommandButtonsModule", launch_view_js)
        self.assertIn("const launchCommandButtonIds", launch_view_js)
        self.assertIn("function setLaunchCommandBusy", launch_view_js)
        self.assertIn("function rejectLaunchCommandWhileBusy", launch_view_js)
        self.assertIn("Another launch command is already in progress.", launch_view_js)
        self.assertNotIn("function renderLaunchAuditProgress", launch_view_preflight_js)
        self.assertNotIn("audit-launch-progress-bars", launch_view_preflight_js)
        self.assertIn("window.mediaPipelineReportsView?.initReportsViewEvents?.();", js)
        self.assertNotIn('if (typeof initReportsViewEvents === "function") initReportsViewEvents();', js)
        self.assertIn("window.mediaPipelineScheduleView?.initScheduleViewEvents?.();", js)
        self.assertNotIn('if (typeof initScheduleViewEvents === "function") initScheduleViewEvents();', js)
        self.assertIn("const maintenanceView = window.mediaPipelineMaintenanceView || {}", js)
        self.assertIn("maintenanceView.initMaintenanceViewEvents?.();", js)
        self.assertIn("maintenanceView.runReleaseDryRun?.()", js)
        self.assertIn("maintenanceView.runBackfillDryRun?.()", js)
        self.assertNotIn('if (typeof initMaintenanceViewEvents === "function") initMaintenanceViewEvents();', js)
        self.assertIn("function collectPipelineStartRequest", launch_view_js)
        self.assertIn('byId("pipeline-start-single-file")', launch_view_js)
        self.assertIn("request.single_file = singleFile", launch_view_js)
        self.assertIn("function browsePipelineSingleFile", launch_view_js)
        self.assertIn('apiPost("/api/pipeline/browse-file", request)', launch_view_js)
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "syncPipelineModeControls")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "selectPipelineModePreset")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "browsePipelineSingleFile")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "clearPipelineSingleFile")
        self.assertNotIn("window.syncPipelineModeControls =", launch_view_js)
        self.assertNotIn("window.selectPipelineModePreset =", launch_view_js)
        self.assertNotIn("window.browsePipelineSingleFile =", launch_view_js)
        self.assertNotIn("window.clearPipelineSingleFile =", launch_view_js)
        self.assertIn("Single-file launch: WebView submits the path only", launch_view_preflight_js)
        self.assertIn("function startPipelineFromForm", launch_view_js)
        self.assertIn("function launchCommandStatusLabel", launch_view_js)
        self.assertIn("function launchCommandResultCorrelationLines", launch_view_js)
        self.assertIn("Command evidence snapshot:", launch_view_js)
        self.assertIn("Diagnostics retry guidance:", launch_view_js)
        self.assertIn("launchCommandDiagnosticsActions(entry)", launch_view_js)
        self.assertIn("Evidence is explanatory only; backend start routes remain authoritative at submission time.", launch_view_js)
        self.assertIn("function formatLaunchCommandDetail", launch_view_js)
        self.assertIn("function renderLaunchCommandResult", launch_view_js)
        self.assertIn("function createLaunchRiskModule", launch_view_risk_js)
        self.assertIn("window.__launchViewRiskModule", launch_view_risk_js)
        self.assertIn("const launchRiskModule = window.__launchViewRiskModule || {}", launch_view_js)
        self.assertIn("delete window.__launchViewRiskModule", launch_view_js)
        self.assertIn("launchRiskModule.createLaunchRiskModule", launch_view_js)
        self.assertIn("function launchSettingsTrustStatus", launch_view_risk_js)
        self.assertIn("function launchSettingsDecision", launch_view_risk_js)
        self.assertIn("function launchSettingsDecisionLines", launch_view_risk_js)
        self.assertIn("function launchSettingsRiskLines", launch_view_risk_js)
        self.assertIn("function launchRealMediaReadinessLines", launch_view_risk_js)
        self.assertIn("function launchSettingsRiskRows", launch_view_risk_js)
        self.assertIn("function launchSettingsRiskDetailLines", launch_view_risk_js)
        self.assertIn("function renderLaunchSettingsRiskHandoff", launch_view_risk_js)
        self.assertIn("Launch Risk Handoff detail:", launch_view_risk_js)
        self.assertIn("Daily-driver rule: resolve blocked rows", launch_view_risk_js)
        self.assertIn("Proof chain:", launch_view_risk_js)
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSettingsWorkspace")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSettingsTrustStatus")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSettingsDecision")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSettingsDecisionLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSettingsRiskLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchRealMediaReadinessLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSettingsRiskRows")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSettingsRiskStatus")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSettingsRiskSummaryLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSettingsRiskDetailLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "renderLaunchSettingsRiskHandoff")
        self.assertNotIn("window.launchSettingsWorkspace =", launch_view_js)
        self.assertNotIn("window.launchSettingsTrustStatus =", launch_view_js)
        self.assertNotIn("window.launchSettingsDecision =", launch_view_js)
        self.assertNotIn("window.launchSettingsDecisionLines =", launch_view_js)
        self.assertNotIn("window.launchSettingsRiskLines =", launch_view_js)
        self.assertNotIn("window.launchRealMediaReadinessLines =", launch_view_js)
        self.assertNotIn("window.launchSettingsRiskRows =", launch_view_js)
        self.assertNotIn("window.launchSettingsRiskStatus =", launch_view_js)
        self.assertNotIn("window.launchSettingsRiskSummaryLines =", launch_view_js)
        self.assertNotIn("window.renderLaunchSettingsRiskHandoff =", launch_view_js)
        self.assertIn("function launchPolicyBoundaryRows", launch_view_risk_js)
        self.assertIn("function renderLaunchPolicyBoundary", launch_view_risk_js)
        self.assertIn("Launch active media-policy boundary:", launch_view_risk_js)
        self.assertIn("Active saved subtitle policy", launch_view_risk_js)
        self.assertIn("Staged subtitle candidate", launch_view_risk_js)
        self.assertIn("Active saved audio policy", launch_view_risk_js)
        self.assertIn("Staged audio candidate", launch_view_risk_js)
        self.assertIn("Active saved publish/source safety", launch_view_risk_js)
        self.assertIn("Staged publish/source candidate", launch_view_risk_js)
        self.assertIn("Launch uses the active saved subtitle, audio, and pending-publish/source-safety policy", launch_view_risk_js)
        self.assertIn("renderLaunchPolicyBoundary()", launch_view_preflight_js)
        self.assertIn("launch-policy-boundary-summary", html)
        self.assertIn("launch-policy-boundary-detail", html)
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchPolicyBoundaryRows")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchPolicyBoundaryStatus")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchPolicyBoundarySummaryLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchPolicyBoundaryDetailLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "renderLaunchPolicyBoundary")
        self.assertNotIn("window.launchPolicyBoundaryStatus =", launch_view_js)
        self.assertNotIn("window.launchPolicyBoundarySummaryLines =", launch_view_js)
        self.assertNotIn("window.launchPolicyBoundaryDetailLines =", launch_view_js)
        self.assertNotIn("window.renderLaunchPolicyBoundary =", launch_view_js)
        self.assertIn("function launchSettingsIntentRows", launch_view_risk_js)
        self.assertIn("function renderLaunchSettingsIntentChecklist", launch_view_risk_js)
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSettingsIntentSummaryLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSettingsIntentDetailLines")
        self.assertNotIn("window.launchSettingsIntentSummaryLines =", launch_view_js)
        self.assertNotIn("window.launchSettingsIntentDetailLines =", launch_view_js)
        self.assertIn("function createLaunchScopeModule", launch_view_scope_js)
        self.assertIn("window.__launchViewScopeModule", launch_view_scope_js)
        self.assertIn("const launchScopeModule = window.__launchViewScopeModule || {}", launch_view_js)
        self.assertIn("delete window.__launchViewScopeModule", launch_view_js)
        self.assertIn("launchScopeModule.createLaunchScopeModule", launch_view_js)
        self.assertIn("function launchScopeReconciliationRows", launch_view_scope_js)
        self.assertIn("function renderLaunchScopeReconciliation", launch_view_scope_js)
        self.assertIn("Launch scope reconciliation:", launch_view_scope_js)
        self.assertIn("visible Queue table, selected Launch mode, cached backend preflight", launch_view_scope_js)
        self.assertIn("Mutation guardrail: this reconciliation is read-only", launch_view_scope_js)
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchScopeReconciliationRows")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchScopeReconciliationStatus")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchScopeReconciliationSummaryLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchScopeReconciliationDetailLines")
        self.assertNotIn("window.launchScopeReconciliationStatus =", launch_view_js)
        self.assertNotIn("window.launchScopeReconciliationSummaryLines =", launch_view_js)
        self.assertNotIn("window.launchScopeReconciliationDetailLines =", launch_view_js)
        self.assertIn("function launchStartDecisionRows", launch_view_scope_js)
        self.assertIn("function renderLaunchStartDecisionSummary", launch_view_scope_js)
        self.assertIn("Launch start decision summary:", launch_view_scope_js)
        self.assertIn("treat Start as sensible only when Launch readiness, backend preflight, Queue, Settings", launch_view_scope_js)
        self.assertIn("Mutation guardrail: this summary is read-only", launch_view_scope_js)
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchStartDecisionStatus")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchStartDecisionSummaryLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchStartDecisionDetailLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "renderLaunchStartDecisionSummary")
        self.assertNotIn("window.launchStartDecisionStatus =", launch_view_js)
        self.assertNotIn("window.launchStartDecisionSummaryLines =", launch_view_js)
        self.assertNotIn("window.launchStartDecisionDetailLines =", launch_view_js)
        self.assertIn("function createLaunchRealMediaModule", launch_view_realmedia_js)
        self.assertIn("window.__launchViewRealMediaModule", launch_view_realmedia_js)
        self.assertIn("const launchRealMediaModule = window.__launchViewRealMediaModule || {}", launch_view_js)
        self.assertIn("delete window.__launchViewRealMediaModule", launch_view_js)
        self.assertIn("launchRealMediaModule.createLaunchRealMediaModule", launch_view_js)
        self.assertIn("function launchRealMediaProofRows", launch_view_realmedia_js)
        self.assertIn("function renderLaunchRealMediaProofHandoff", launch_view_realmedia_js)
        self.assertIn("Launch real-media sample proof handoff:", launch_view_realmedia_js)
        self.assertIn("Home Real-Media Validation Worksheet", launch_view_realmedia_js)
        self.assertIn("daily-driver trust still requires post-run output", launch_view_realmedia_js)
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchWorksheetRunRows")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchWorksheetRunsMatchingSample")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchPolicyAlignmentPayload")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchPolicyAlignmentRows")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchRealMediaProofRows")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchRealMediaProofStatus")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchRealMediaProofSummaryLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchRealMediaProofDetailLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "renderLaunchRealMediaProofHandoff")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSampleSetCoverageLine")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSampleValidationRecordRows")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSampleValidationRecordsMatchingSample")
        self.assertNotIn("window.launchWorksheetRunRows =", launch_view_js)
        self.assertNotIn("window.launchWorksheetRunsMatchingSample =", launch_view_js)
        self.assertNotIn("window.launchPolicyAlignmentPayload =", launch_view_js)
        self.assertNotIn("window.launchPolicyAlignmentRows =", launch_view_js)
        self.assertNotIn("window.launchRealMediaProofRows =", launch_view_js)
        self.assertNotIn("window.launchRealMediaProofStatus =", launch_view_js)
        self.assertNotIn("window.launchRealMediaProofSummaryLines =", launch_view_js)
        self.assertNotIn("window.launchRealMediaProofDetailLines =", launch_view_js)
        self.assertNotIn("window.launchSampleSetCoverageLine =", launch_view_js)
        self.assertNotIn("window.launchSampleValidationRecordRows =", launch_view_js)
        self.assertNotIn("window.launchSampleValidationRecordsMatchingSample =", launch_view_js)
        self.assertIn("function launchSampleExecutionRows", launch_view_realmedia_js)
        self.assertIn("function renderLaunchSampleExecutionChecklist", launch_view_realmedia_js)
        self.assertIn("Launch sample execution checklist:", launch_view_realmedia_js)
        self.assertIn("Home's backend-authored operator sample execution checklist", launch_view_realmedia_js)
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSampleExecutionStatus")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSampleExecutionSummaryLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchSampleExecutionDetailLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "renderLaunchSampleExecutionChecklist")
        self.assertNotIn("window.launchSampleExecutionStatus =", launch_view_js)
        self.assertNotIn("window.launchSampleExecutionSummaryLines =", launch_view_js)
        self.assertNotIn("window.launchSampleExecutionDetailLines =", launch_view_js)
        self.assertIn("function createLaunchPreflightModule", launch_view_preflight_js)
        self.assertIn("window.__launchViewPreflightModule", launch_view_preflight_js)
        self.assertIn("const launchPreflightModule = window.__launchViewPreflightModule || {}", launch_view_js)
        self.assertIn("delete window.__launchViewPreflightModule", launch_view_js)
        self.assertIn("launchPreflightModule.createLaunchPreflightModule", launch_view_js)
        self.assertIn("function launchPilotRunReadinessRows", launch_view_preflight_js)
        self.assertIn("function renderLaunchPilotRunReadiness", launch_view_preflight_js)
        self.assertIn("Launch pilot run readiness:", launch_view_preflight_js)
        self.assertIn("selected Queue sample, saved Settings policy, backend preflight, pilot category, pending-publish posture, and post-run proof plan", launch_view_preflight_js)
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchPilotRunReadinessStatus")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchPilotRunReadinessSummaryLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchPilotRunReadinessDetailLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "renderLaunchPilotRunReadiness")
        self.assertNotIn("window.launchPilotRunReadinessStatus =", launch_view_js)
        self.assertNotIn("window.launchPilotRunReadinessSummaryLines =", launch_view_js)
        self.assertNotIn("window.launchPilotRunReadinessDetailLines =", launch_view_js)
        self.assertIn("function launchBackendPreflightRows", launch_view_preflight_js)
        self.assertIn("function getLastLaunchBackendPreflightPayloads", launch_view_preflight_js)
        self.assertIn("function launchBackendPreflightPayloadForTarget", launch_view_preflight_js)
        self.assertIn("function getLastLaunchBackendPreflightRefreshInfo", launch_view_preflight_js)
        self.assertIn("function refreshLaunchBackendPreflight", launch_view_preflight_js)
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchBackendPreflightRows")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "getLastLaunchBackendPreflightPayloads")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchBackendPreflightPayloadForTarget")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "getLastLaunchBackendPreflightRefreshInfo")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchBackendPreflightSummaryLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "launchBackendPreflightDetailLines")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "renderLaunchBackendPreflight")
        _assert_namespace_export(self, launch_view_js, "mediaPipelineLaunchView", "refreshLaunchBackendPreflight")
        self.assertNotIn("window.launchBackendPreflightRows =", launch_view_js)
        self.assertNotIn("window.getLastLaunchBackendPreflightPayloads =", launch_view_js)
        self.assertNotIn("window.launchBackendPreflightPayloadForTarget =", launch_view_js)
        self.assertNotIn("window.getLastLaunchBackendPreflightRefreshInfo =", launch_view_js)
        self.assertNotIn("window.launchBackendPreflightSummaryLines =", launch_view_js)
        self.assertNotIn("window.launchBackendPreflightDetailLines =", launch_view_js)
        self.assertNotIn("window.renderLaunchBackendPreflight =", launch_view_js)
        self.assertNotIn("window.refreshLaunchBackendPreflight =", launch_view_js)
        self.assertIn("launch-backend-preflight-refresh-button", html)
        self.assertIn("Refresh Backend Preflight", html)
        self.assertIn("Last refresh:", launch_view_preflight_js)
        self.assertIn("fetch_failure_count", launch_view_preflight_js)
        self.assertIn("renderQueueLaunchDecisionChecklist()", launch_view_preflight_js)
        self.assertIn("/api/launch/preflight", launch_view_preflight_js)
        self.assertIn("GET /api/launch/preflight", launch_view_preflight_js)
        self.assertIn("Continuous schedule-stop watcher", launch_readiness_view_js)
        self.assertIn("This read route mirrors backend launch guards without journaling commands or mutating runtime state", launch_view_preflight_js)
        self.assertIn("Mutation guardrail: this panel cannot launch, reserve locks, clear flags, save settings, drain, rename, repair, delete, publish, or touch media files.", launch_view_preflight_js)
        self.assertIn("Saved settings evidence:", launch_view_risk_js)
        self.assertIn("Launch settings evidence snapshot:", launch_view_risk_js)
        self.assertIn("Launch settings risk handoff:", launch_view_risk_js)
        self.assertIn("Real-media validation boundary", launch_view_risk_js)
        self.assertIn("Preview/build/release checks prove shell/package readiness only", launch_view_risk_js)
        self.assertIn("Real-media proof still requires a completed sample run", launch_view_risk_js)
        self.assertIn("Saved settings vs launch intent checklist:", launch_view_risk_js)
        self.assertIn("Launch uses saved backend settings and selected form intent only", launch_view_risk_js)
        self.assertIn("unsaved Settings changes do not count until Save Settings succeeds", launch_view_risk_js)
        self.assertIn("Queue display scope", launch_view_risk_js)
        self.assertIn("Do not treat the visible Queue table as launch scope", launch_view_risk_js)
        self.assertIn("Launch start requests do not include Queue filter text", launch_view_risk_js)
        self.assertIn("Backend Launch remains authoritative for queue scope", launch_view_risk_js)
        self.assertIn("queueCurrentFilterScope(queueRows)", launch_view_risk_js)
        self.assertIn("Mutation guardrail: this checklist is read-only and cannot launch, save settings, drain, rename, repair, delete, publish, or touch media files.", launch_view_risk_js)
        self.assertIn("renderLaunchSettingsIntentChecklist(pipelineRequest)", launch_view_preflight_js)
        self.assertIn("refreshLaunchBackendPreflight()", launch_view_js)
        self.assertIn("renderLaunchSettingsIntentChecklist()", command_history_js)
        self.assertIn("This panel translates saved settings posture into launch-specific operator checks.", launch_view_risk_js)
        self.assertIn("Evidence guidance:", launch_view_risk_js)
        self.assertIn("Evidence owner: Settings page edits/save; Launch page displays saved posture only.", launch_view_risk_js)
        self.assertIn("Backend risk summary:", launch_view_risk_js)
        self.assertIn("Deferred publish:", launch_view_risk_js)
        self.assertIn("PATH tool fallback:", launch_view_risk_js)
        self.assertIn("H.264 copy / remux precision", launch_view_risk_js)
        self.assertIn("Container / original subtitle preservation", launch_view_risk_js)
        self.assertIn("Plex-compatible H.264 sources should remain copy/remux candidates", launch_view_risk_js)
        self.assertIn("MP4 cannot carry every original subtitle format", launch_view_risk_js)
        self.assertIn("normal growth=${maxGrowth}%", launch_view_risk_js)
        self.assertIn("renderLaunchSettingsRiskHandoff(pipelineRequest)", launch_view_preflight_js)
        self.assertIn("Do not launch media work with drop-without-convert subtitle contradictions.", launch_view_risk_js)
        self.assertIn("No-audio output is unsafe for normal Plex publishing", launch_view_risk_js)
        self.assertIn("Backend launch validation, process locks, and Settings Save remain the source of truth.", launch_view_risk_js)
        self.assertIn("function pipelineLaunchPreflightLines", launch_view_preflight_js)
        self.assertNotIn("function auditLaunchPreflightLines", launch_view_preflight_js)
        self.assertIn("function rerunLaunchPreflightLines", launch_view_preflight_js)
        self.assertIn("const launchReadinessView = window.mediaPipelineLaunchReadinessView || {}", launch_view_preflight_js)
        self.assertIn("launchReadinessView.getLastLaunchReadinessPayload()", launch_view_preflight_js)
        self.assertIn("launchReadinessView.renderLaunchReadiness({", launch_view_preflight_js)
        self.assertIn("renderLaunchTimingTrust()", launch_view_preflight_js)
        self.assertIn("renderScheduleTimingTrust()", launch_view_preflight_js)
        self.assertIn("const scheduleView = window.mediaPipelineScheduleView || {}", launch_view_js)
        self.assertIn("renderScheduleTimingTrust: typeof renderScheduleTimingTrust === \"function\" ? renderScheduleTimingTrust : null", launch_view_js)
        self.assertIn("function initLaunchViewEvents", launch_view_js)
        self.assertIn("function initLaunchTabNav", launch_view_js)
        self.assertIn("function activateLaunchTab", launch_view_js)
        self.assertIn("mediapipeline-launch-tab", launch_view_js)
        self.assertIn("Backend validation and launch locking remain the source of truth.", launch_view_preflight_js)
        self.assertIn("operator_readiness", launch_view_preflight_js)
        self.assertIn("Plan only: ${request.plan_only ? \"yes - no manifest or media writes\" : \"no\"}", launch_view_preflight_js)
        self.assertIn("Dry run: ${request.dry_run ? \"yes - evidence-writing preview\" : request.plan_only ? \"no - plan-only request\" : \"no - live rerun start\"}", launch_view_preflight_js)
        self.assertIn("Safety policy: plan-only stops before writing manifests, temp config, staging files, parked outputs, or source media.", launch_view_preflight_js)
        self.assertIn("Safety policy: dry-run preview should produce backend evidence without staging, moving, publishing, or touching media.", launch_view_preflight_js)
        self.assertIn("Safety policy: live rerun copies to scratch, keeps originals, and parks returned outputs.", launch_view_preflight_js)
        self.assertIn("commandResultDisplayMessage(payload)", launch_view_js)
        self.assertIn("window.mediaPipelineContractView", contract_view_js)
        self.assertIn("function renderContract", contract_view_js)
        self.assertIn("function renderContractRows", contract_view_js)
        self.assertIn("function contractSafetyReviewRows", contract_view_js)
        self.assertIn("function renderContractSafetyReview", contract_view_js)
        self.assertIn("function initContractViewEvents", contract_view_js)
        self.assertNotIn("window.initContractViewEvents = initContractViewEvents", contract_view_js)
        self.assertIn("Mutation guardrail: WebView controls must use backend-owned routes", contract_view_js)
        self.assertIn("Contract safety review:", contract_view_js)
        self.assertIn("Decision rule: blocked rows must be fixed before trusting new WebView controls", contract_view_js)
        self.assertIn("Network lifecycle boundary", contract_view_js)
        self.assertIn("Use backend dry-run lifecycle checks first; confirmed Network lifecycle routes remain provider-guarded", contract_view_js)
        self.assertIn("Repair/reconcile boundary", contract_view_js)
        self.assertIn("Backend dry-runs exist for evidence review; mutation controls remain forbidden", contract_view_js)
        self.assertIn("backend dry-runs exist but mutation controls remain forbidden", contract_view_js)
        self.assertIn("Dry-run contract fields", contract_view_js)
        self.assertIn("Rollback journal fields", contract_view_js)
        self.assertIn("Source policy: source media mutation", contract_view_js)
        self.assertIn("Route exposure gates", contract_view_js)
        self.assertIn("repair_reconcile_contracts", contract_view_js)
        self.assertIn("repair_reconcile_summary", contract_view_js)
        self.assertIn("network_lifecycle_contracts", contract_view_js)
        self.assertIn("network_lifecycle_summary", contract_view_js)
        self.assertIn("WebView shells must keep tokens on all read, command, open, process, settings, rename, and publish routes", contract_view_js)
        self.assertIn("Frontend code stages intent and displays results only", contract_view_js)
        self.assertIn("this panel is read-only", contract_view_js)
        self.assertIn("Operator safety: this is a guarded backend-owned action", contract_view_js)
        self.assertIn("Route contract JSON", contract_view_js)
        self.assertIn("jsonDetailText({", contract_view_js)
        self.assertIn("formats already-loaded route data only", contract_view_js)
        _assert_namespace_export(self, contract_view_js, "mediaPipelineContractView", "contractSafetyReviewRows")
        self.assertIn("api-contract-rows", contract_view_js)
        self.assertIn("api-contract-safety-rows", contract_view_js)
        self.assertIn("api-contract-detail", contract_view_js)
        self.assertIn("allowed_row_scopes", contract_view_js)
        self.assertIn("Allowed row scopes:", contract_view_js)
        self.assertIn("Backend data:", launch_view_js)
        self.assertIn("Submitted request:", launch_view_js)
        self.assertIn("pending-drain-detail", launch_view_js)
        self.assertIn("/api/pipeline/start", launch_view_js)
        self.assertNotIn("function collectAuditStartRequest", launch_view_js)
        self.assertNotIn("function startAuditFromForm", launch_view_js)
        self.assertNotIn("function renderLaunchAuditControls", launch_view_js)
        self.assertNotIn("/api/audit/", launch_view_js)
        self.assertNotIn("renderLaunchAuditIssueRows", launch_view_js)
        self.assertNotIn("function renderLaunchAuditLog", launch_view_js)
        self.assertNotIn("renderLaunchAuditControls", launch_view_js)
        self.assertNotIn("renderLaunchAuditLog", launch_view_js)
        self.assertIn("function collectRerunStartRequest", launch_view_js)
        self.assertIn("function startRerunFromForm", launch_view_js)
        self.assertIn("/api/rerun/start", launch_view_js)
        self.assertIn("rerun-plan-only-button", html)
        self.assertIn("Plan CSV Rerun", html)
        self.assertIn("rerun-dry-run-button", html)
        self.assertIn("Preview CSV Rerun", html)
        self.assertIn('startRerunFromForm({ plan_only: true })', js)
        self.assertIn('startRerunFromForm({ dry_run: true })', js)
        self.assertIn('startRerunFromForm({ dry_run: false })', js)
        self.assertIn('stage_mode: "copy"', launch_view_js)
        self.assertIn('original_mode: "keep"', launch_view_js)
        self.assertIn('return_mode: "park"', launch_view_js)
        self.assertIn('mode: "drain_pending_pushes"', launch_view_js)
        self.assertIn('command: "pending_publish.drain"', launch_view_js)
        self.assertIn('typeof pendingDrainGuardState === "function" ? pendingDrainGuardState() : null', launch_view_js)
        self.assertIn("frontend_guard: true", launch_view_js)
        self.assertIn("guard?.confirm_message", launch_view_js)
        self.assertIn("function renderLaunchReadinessPanel", js)
        self.assertIn("window.mediaPipelineLaunchReadinessView?.renderLaunchReadiness?.(payload)", js)
        self.assertIn("renderLaunchReadinessPanel({", js)
        self.assertIn("settings: getLastSettings()", js)
        self.assertIn("settings: values.settings || getLastSettings()", js)
        self.assertIn("startupProgressLines", js)
        self.assertIn("bootstrap.startupProgress", js)
        self.assertIn('refreshGet("/api/health", refreshOptions)', js)
        self.assertIn("values.health?.startup_progress", js)
        self.assertIn('tr[data-status="changed"]', css_components)
        self.assertIn('tr[data-status="unknown"]', css_components)
        self.assertIn('tr[data-status="unchanged"]', css_components)
        self.assertIn('.panel-heading strong[data-state="blocked"]', css_components)
        self.assertIn('.panel-heading strong[data-state="ready"]', css_components)
        self.assertIn(".close-readiness", css_layout)
        self.assertIn('.close-readiness[data-state="blocked"]', css_layout)
        self.assertIn(".refresh-health", css_layout)
        self.assertIn('.refresh-health[data-state="warning"]', css_layout)
        self.assertIn('.refresh-health[data-state="updating"]', css_layout)
        self.assertIn("function selectedRowAtAGlanceLines", dom_helpers_js)
        self.assertIn("selectedRowAtAGlanceLines,", dom_helpers_js)
        self.assertIn("function reviewFlagExplanationLines", dom_helpers_js)
        self.assertIn("reviewFlagExplanationLines,", dom_helpers_js)
        self.assertIn("expected output proof is missing", dom_helpers_js)
        self.assertIn("translate already-loaded backend markers", dom_helpers_js)
        self.assertIn("function selectedRowDetailDrawerLines", dom_helpers_js)
        self.assertIn("selectedRowDetailDrawerLines,", dom_helpers_js)
        self.assertIn("function payloadFreshnessLines", dom_helpers_js)
        self.assertIn("payloadFreshnessLines,", dom_helpers_js)
        self.assertIn("function renderOpenTargetActionGroups", dom_helpers_js)
        self.assertIn("renderOpenTargetActionGroups,", dom_helpers_js)
        self.assertIn('Object.defineProperty(payload, "__mediaPipelineRefreshMeta"', js)
        self.assertIn("function initPageRefreshButtons", js)
        self.assertIn("[data-page-refresh-button]", js)
        self.assertIn('id="completed-refresh-current-output-button"', html)
        self.assertIn('data-page-refresh-button="pending"', html)
        self.assertIn('data-page-refresh-button="diagnostics"', html)
        self.assertIn("payloadFreshnessLines({", queue_view_summary_js)
        self.assertIn('label: "Queue"', queue_view_summary_js)
        self.assertIn("payloadFreshnessLines({", completed_view_js)
        self.assertIn('label: "Output"', completed_view_js)
        self.assertIn("payloadFreshnessLines({", pending_publish_view_js)
        self.assertIn('label: "Pending Publish"', pending_publish_view_js)
        self.assertIn("payloadFreshnessLines({", diagnostics_view_js)
        self.assertIn('label: "Diagnostics"', diagnostics_view_js)
        self.assertIn("payloadFreshnessLines({", diagnostics_state_summary_view_js)
        self.assertIn('label: "Diagnostics State"', diagnostics_state_summary_view_js)
        self.assertIn("/api/snapshot", js)
        self.assertIn("/api/backend/close-readiness", js)
        self.assertIn("/api/backend/shutdown", js)
        self.assertIn("function renderBackendLifecycle", js)
        self.assertIn("function requestBackendShutdown", js)
        self.assertIn("function renderBackendLifecycleHistory", js)
        self.assertIn("function backendLifecycleCommandEntries", js)
        self.assertIn("function initEvidenceToggle", js)
        self.assertIn("mediapipeline-evidence-hidden", js)
        self.assertIn("document.body.classList.toggle(\"evidence-hidden\", hidden)", js)
        self.assertIn("initEvidenceToggle()", js)
        self.assertIn("function keyboardShortcutRegistry", js)
        self.assertIn("function focusActivePageSearch", js)
        self.assertIn("function clearActivePageFilters", js)
        self.assertIn("function moveActivePageSelection", js)
        self.assertIn("function focusActivePageDetail", js)
        self.assertIn("Read-only shortcuts. They navigate, refresh, filter, focus, or select rows", js)
        self.assertIn('key: "/"', js)
        self.assertIn('key: "c"', js)
        self.assertIn('key: "j"', js)
        self.assertIn('key: "k"', js)
        self.assertIn('key: "d"', js)
        self.assertIn("function closeReadinessWatcherSummary", js)
        self.assertIn("Continuous watcher:", js)
        self.assertIn("Watcher note: keep the backend alive", js)
        self.assertIn("Another backend shutdown command is already in progress.", js)
        self.assertIn("WebView exposes backend shutdown only when the loaded close-readiness payload reports safe.", js)
        self.assertIn("Lifecycle command history is evidence only", js)
        self.assertIn('body.evidence-hidden .panel[data-panel-type="evidence"]:not([data-evidence-toggle-exempt="true"])', css_components)
        self.assertIn("/api/diagnostics/state-summary", js)
        self.assertIn("/api/commands", js)
        self.assertIn("/api/contract", js)
        self.assertIn("/api/completed", js)
        self.assertIn("/api/failures", js)
        self.assertIn("/api/audit-results", js)
        self.assertIn("/api/pending-publish", js)
        self.assertIn("/api/schedule", js)
        self.assertIn("/api/settings/workspace", js)
        self.assertIn("window.getLastSnapshot = () => lastSnapshot", js)
        self.assertNotIn("renderLaunchAuditProgress(lastSnapshot)", js)
        self.assertIn("const pendingPublishPayload = values[\"pending publish\"] || (pendingPublishFailure ? {", js)
        self.assertIn("if (values[\"pending publish\"] || pendingPublishFailure) renderPendingPublish(pendingPublishPayload, values.snapshot || lastSnapshot)", js)
        self.assertIn("window.mediaPipelineProgressView?.renderProgressBars?.(Array.isArray(snapshot.progress_bars)", js)
        self.assertIn("window.mediaPipelineProgressView?.renderProgressDetails?.(snapshot.progress || {})", js)
        self.assertIn("window.mediaPipelineProgressView?.renderDiagnosticsProgress?.(lastSnapshot)", js)
        self.assertIn("renderDiagnosticsStateSummaryFn(values[\"diagnostics state summary\"])", js)
        self.assertIn("const recentEvents = Array.isArray(snapshot.recent_events)", js)
        self.assertIn("mediaPipelineProgressView?.renderPipelineEvents?.(recentEvents)", js)
        self.assertIn("renderTopbarEventTicker(snapshot)", js)
        self.assertIn("window.setTopbarPendingLaunch = setTopbarPendingLaunch", js)
        self.assertIn("const telemetryOptions = {", js)
        self.assertIn("refreshIntervalMs: AUTOMATIC_REFRESH_INTERVAL_MS", js)
        self.assertIn("? renderTelemetrySafely(values.telemetry, telemetryOptions)", js)
        self.assertIn('unavailableReason: telemetryFailure?.message || "telemetry route returned no payload"', js)
        self.assertIn("renderQueueRows", js)
        self.assertIn('const queueStatusFilter = byId("queue-status-filter")', js)
        self.assertIn('queueStatusFilter.addEventListener("change", () => window.mediaPipelineQueueView?.renderQueueRows?.())', js)
        self.assertIn('const queueInvestigationFilter = byId("queue-investigation-filter")', js)
        self.assertIn('queueInvestigationFilter.addEventListener("change", () => window.mediaPipelineQueueView?.renderQueueRows?.())', js)
        self.assertIn("function renderQueueReviewDigest", queue_view_js)
        self.assertIn("function queueReviewDigestStatus", queue_view_js)
        self.assertIn('<pre id="queue-filter-summary" class="prose-block queue-filter-summary" hidden aria-hidden="true">', html)
        self.assertIn("summary.hidden = true", queue_view_js)
        self.assertIn("queue-status-filter", html)
        self.assertIn("queue-investigation-filter", html)
        self.assertIn("queue-selected-status", html)
        self.assertIn("queue-selected-summary", html)
        self.assertIn("function queueTableRowStatus", queue_view_js)
        self.assertIn("function queueMatchesInvestigationFilter", queue_view_js)
        self.assertIn("function queueIsHiddenSidecarBlockedRow", queue_view_js)
        self.assertIn("Hidden subtitle sidecars", queue_view_js)
        self.assertIn("function queueInvestigationFilterLabel", queue_view_js)
        self.assertIn("function renderQueueSelectedAtAGlance", queue_view_js)
        self.assertIn("function queueSelectedAtAGlanceLines", queue_view_js)
        self.assertIn("window.mediaPipelineDom?.selectedRowAtAGlanceLines", queue_view_js)
        self.assertIn("window.mediaPipelineDom?.selectedRowDetailDrawerLines", queue_view_js)
        self.assertIn("Queue selected-row detail", queue_view_js)
        self.assertIn("reviewFlagExplanationLines(reviewFlags", queue_view_js)
        self.assertIn("No Queue review flags were reported for this row.", queue_view_js)
        self.assertIn("Authority: this summary is read-only. It cannot launch", queue_view_js)
        self.assertIn('byId("queue-status-filter")', queue_view_js)
        self.assertIn('byId("queue-investigation-filter")', queue_view_js)
        self.assertIn("filterResultSummaryLines", queue_view_js)
        self.assertIn("buildFilterSummary({", queue_view_js)
        self.assertIn("filterRowsByInvestigation(statusRows, investigationFilter, queueMatchesInvestigationFilter)", queue_view_js)
        self.assertIn("${renderedCount} shown / ${rows.length} filtered / ${lastQueueRows.length} rows", queue_view_js)
        self.assertIn('decisionName: "launch"', queue_view_js)
        self.assertIn("Queue review rows", queue_view_js)
        self.assertIn("selectQueueRow(item)", queue_view_js)
        self.assertIn("renderCompleted", js)
        self.assertIn("renderCompletedRows", js)
        self.assertIn("completed-inventory-progress-bars", html)
        self.assertIn("function renderCompletedInventoryProgress", completed_view_status_boards_js)
        self.assertIn("function completedInventoryProgressBars", completed_view_status_boards_js)
        self.assertIn('renderProgressBarsInto("completed-inventory-progress-bars"', completed_view_status_boards_js)
        self.assertIn('"/api/completed?limit=100"', js)
        self.assertIn('"/api/completed?limit=all&force_refresh=true&proof=live"', js)
        self.assertIn('const completedStatusFilter = byId("completed-status-filter")', js)
        self.assertIn('completedStatusFilter.addEventListener("change", () => window.mediaPipelineCompletedView?.renderCompletedRows?.())', js)
        self.assertIn('const completedLibraryFilter = byId("completed-library-filter")', js)
        self.assertIn('completedLibraryFilter.addEventListener("change", () => window.mediaPipelineCompletedView?.renderCompletedRows?.())', js)
        self.assertIn('const completedInvestigationFilter = byId("completed-investigation-filter")', js)
        self.assertIn('completedInvestigationFilter.addEventListener("change", () => window.mediaPipelineCompletedView?.renderCompletedRows?.())', js)
        self.assertIn('const completedHistoryFilter = byId("completed-history-filter")', js)
        self.assertIn('const completedHistoryStatusFilter = byId("completed-history-status-filter")', js)
        self.assertIn('const completedHistoryInvestigationFilter = byId("completed-history-investigation-filter")', js)
        self.assertIn("function renderCompletedReviewDigest", completed_view_review_js)
        self.assertIn("function completedReviewDigestStatus", completed_view_review_js)
        self.assertIn("completed-filter-summary", html)
        self.assertIn("completed-status-filter", html)
        self.assertIn("completed-library-filter", html)
        self.assertIn("completed-investigation-filter", html)
        self.assertIn("completed-history-filter-summary", html)
        self.assertIn("completed-history-status-filter", html)
        self.assertIn("completed-history-investigation-filter", html)
        self.assertIn("completed-selected-status", html)
        self.assertIn("completed-selected-summary", html)
        self.assertIn("completed-raw-detail", html)
        self.assertIn('id="completed-selected-summary" class="completed-selected-summary"', html)
        self.assertIn("Raw selected-row detail", html)
        self.assertIn("function completedTableRowStatus", completed_view_review_js)
        self.assertIn("function completedHasSmallHealthySizeDelta", completed_view_review_js)
        self.assertIn("function completedMatchesInvestigationFilter", completed_view_review_js)
        self.assertIn("function completedInvestigationFilterLabel", completed_view_review_js)
        self.assertIn("function renderCompletedSelectedAtAGlance", completed_view_review_js)
        self.assertIn("function completedSelectedAtAGlanceLines", completed_view_review_js)
        self.assertIn("function completedSelectedSummaryNodes", completed_view_review_js)
        self.assertIn("summaryNode.replaceChildren", completed_view_review_js)
        self.assertIn("completed-selected-decision-strip", completed_view_review_js)
        self.assertIn("function completedSelectedDiagnosisLine", completed_view_review_js)
        self.assertIn("function completedSelectedEvidenceGaps", completed_view_review_js)
        self.assertIn("function completedSelectedNextChecks", completed_view_review_js)
        self.assertIn("Why this output looks different", completed_view_review_js)
        self.assertIn("Trigger / route reason", completed_view_review_js)
        self.assertIn("Runtime/log evidence", completed_view_review_js)
        self.assertIn("What to check next", completed_view_review_js)
        self.assertIn("window.mediaPipelineDom?.selectedRowAtAGlanceLines", completed_view_review_js)
        self.assertIn("selectedRowDetailDrawerLines", completed_view_selection_js)
        self.assertIn("Completed selected-row detail", completed_view_selection_js)
        self.assertIn("reviewFlagExplanationLines(reviewMarkers", completed_view_review_js)
        self.assertIn("No Completed review flags or consistency issues were reported for this row.", completed_view_review_js)
        self.assertIn("Authority: this summary is read-only. It cannot accept outputs", completed_view_review_js)
        self.assertIn('byId("completed-status-filter")', completed_view_filters_js)
        self.assertIn('byId("completed-library-filter")', completed_view_filters_js)
        self.assertIn('byId("completed-investigation-filter")', completed_view_filters_js)
        self.assertIn('byId("completed-history-status-filter")', completed_view_filters_js)
        self.assertIn('byId("completed-history-investigation-filter")', completed_view_filters_js)
        self.assertIn("filterResultSummaryLines({", completed_view_table_js)
        self.assertIn("filterRowsByInvestigation(statusRows, investigationFilter, completedMatchesInvestigationFilter)", completed_view_filters_js)
        self.assertIn("function completedLibraryMatchesFilter", completed_view_filters_js)
        self.assertIn("${renderedRows} shown / ${visibleRows} filtered / ${totalRows} rows", completed_view_filters_js)
        self.assertIn("filtering Current Output Status does not mark outputs accepted", completed_view_table_js)
        self.assertIn("filtering Completed history does not mark outputs accepted", completed_view_table_js)
        self.assertIn("Completed review rows", completed_view_review_js)
        self.assertIn("ctx.selectCompletedRow(item)", completed_view_table_js)
        self.assertIn("requestCompletedOpen", js)
        self.assertIn("renderPendingRows", js)
        self.assertIn('const pendingStatusFilter = byId("pending-status-filter")', js)
        self.assertIn('pendingStatusFilter.addEventListener("change", () => window.mediaPipelinePendingPublishView?.renderPendingRows?.())', js)
        self.assertIn('const pendingInvestigationFilter = byId("pending-investigation-filter")', js)
        self.assertIn('pendingInvestigationFilter.addEventListener("change", () => window.mediaPipelinePendingPublishView?.renderPendingRows?.())', js)
        self.assertIn("function renderPendingReviewDigest", pending_publish_view_js)
        self.assertIn("function pendingReviewDigestStatus", pending_publish_view_js)
        self.assertIn("pending-filter-summary", html)
        self.assertIn("pending-inventory-progress-bars", html)
        self.assertIn("function renderPendingInventoryProgress", pending_publish_view_js)
        self.assertIn("function pendingInventoryProgressBars", pending_publish_view_js)
        self.assertIn('renderProgressBarsInto("pending-inventory-progress-bars"', pending_publish_view_js)
        self.assertIn("pending-file-inventory-status", html)
        self.assertIn("pending-file-inventory-summary", html)
        self.assertIn("pending-file-inventory-rows", html)
        self.assertIn("function renderPendingFileInventory", pending_publish_view_js)
        self.assertIn("Pending parked file inventory:", pending_publish_view_js)
        self.assertIn("directory listing only; file bytes were not read and no files were changed", pending_publish_view_js)
        self.assertIn("pending-status-filter", html)
        self.assertIn("pending-investigation-filter", html)
        self.assertIn("pending-selected-status", html)
        self.assertIn("pending-selected-summary", html)
        self.assertIn("function pendingTableRowStatus", pending_publish_view_js)
        self.assertIn("function pendingMatchesInvestigationFilter", pending_publish_view_js)
        self.assertIn("function pendingInvestigationFilterLabel", pending_publish_view_js)
        self.assertIn("function renderPendingSelectedAtAGlance", pending_publish_view_js)
        self.assertIn("function pendingSelectedAtAGlanceLines", pending_publish_view_js)
        self.assertIn("Authority: this summary is read-only. It cannot drain", pending_publish_view_js)
        self.assertIn('byId("pending-status-filter")', pending_publish_view_js)
        self.assertIn('byId("pending-investigation-filter")', pending_publish_view_js)
        self.assertIn("filterResultSummaryLines({", pending_publish_view_js)
        self.assertIn("filterRowsByInvestigation(statusRows, investigationFilter, pendingMatchesInvestigationFilter)", pending_publish_view_js)
        self.assertIn("${renderedCount} shown / ${rows.length} filtered / ${lastPendingRows.length} rows", pending_publish_view_js)
        self.assertIn("filtering Pending Publish rows does not change drain scope", pending_publish_view_js)
        self.assertIn("Pending publish review rows", pending_publish_view_js)
        self.assertIn("selectPendingRow(item)", pending_publish_view_js)
        self.assertIn("startPendingPublishDrain", launch_view_js)
        self.assertIn("initSettingsViewEvents", js)
        self.assertIn("initLaunchViewEvents", js)
        self.assertIn("initDiagnosticsViewEvents", js)
        self.assertIn("window.mediaPipelineContractView?.initContractViewEvents?.();", js)
        self.assertNotIn("initContractViewEvents();", js)
        self.assertIn("renderSettings(values.settings)", js)
        self.assertIn("window.mediaPipelineLaunchView?.renderAllLaunchPreflights?.();", js)
        self.assertNotIn("window.mediaPipelineLaunchView?.renderLaunchAuditLog?.(values[\"audit results\"])", js)
        self.assertIn("window.mediaPipelineReportsView?.renderAuditControls?.(values[\"audit controls\"])", js)
        self.assertNotIn("window.mediaPipelineLaunchView?.renderLaunchAuditControls?.(values[\"audit controls\"])", js)
        self.assertIn("function showPage", js)
        self.assertIn("window.showPage = showPage;", js)
        self.assertIn("const crossPageContext = {", js)
        self.assertIn("renderCrossPageContext(crossPageContext)", js)
        self.assertIn("window.mediaPipelineLaunchView?.renderLaunchRealMediaProofHandoff?.(crossPageContext)", js)
        self.assertIn("function renderDailyDriverReadiness", js)
        self.assertIn("function dailyDriverRows", js)
        self.assertIn("function dailyDriverRealMediaProofRow", js)
        self.assertIn("function dailyDriverSummaryLines", js)
        self.assertIn("function renderTopbarActivity", js)
        self.assertIn("function topbarCurrentWorkMeta", js)
        self.assertIn("activity-meta", js)
        self.assertIn("topbarCleanCurrentName", js)
        self.assertNotIn("function topbarOriginalCurrentName", js)
        self.assertIn('id="topbar-event-ticker" aria-live="polite"', html)
        self.assertIn("function renderTopbarEventTicker", app_lifecycle_js)
        self.assertIn("function setTopbarPendingLaunch", app_lifecycle_js)
        self.assertIn("topbarEventTickerLine", app_lifecycle_js)
        self.assertIn("pipeline.start accepted", app_lifecycle_js)
        self.assertIn("waiting for backend event", app_lifecycle_js)
        self.assertIn(".topbar-event-ticker", css_layout)
        self.assertIn('text-overflow: ellipsis;', css_layout)
        self.assertIn('.topbar-event-ticker[data-state="pending"]', css_layout)
        self.assertIn("window.setTopbarPendingLaunch?.({ pid })", launch_view_js)
        self.assertIn("function updatePagePanelEmptyStates", js)
        self.assertIn("data-page-empty-state", js)
        self.assertIn("No boxes are visible on this tab.", js)
        self.assertIn("Boxes may be hidden by", js)
        self.assertIn("function renderHomeNextQueue", js)
        self.assertIn("function homeNextQueueRows", js)
        self.assertIn("function homeQueueRowIsRunnable", js)
        self.assertIn("home-next-queue-list", js)
        self.assertIn("Next 5 Videos", html)
        self.assertIn("Run Progress", html)
        self.assertIn("Recently Completed", html)
        self.assertIn("renderHomeNextQueue(dashboardContext)", js)
        self.assertIn("failuresPayload: values.failures || {}", js)
        self.assertIn("auditResults: values[\"audit results\"] || {}", js)
        self.assertIn("Daily-driver readiness checklist:", js)
        self.assertIn("Real-media sample proof", js)
        self.assertIn("function externalDependencyRows", js)
        self.assertIn("function renderExternalDependencyDigest", js)
        self.assertIn("window.externalDependencyEvidenceText", js)
        self.assertIn("External dependency digest:", js)
        self.assertIn("Settings BDPGS OCR paths", js)
        self.assertIn("Settings VobSub OCR paths", js)
        self.assertIn("Settings raw-key action plan", js)
        self.assertIn("stage or save settings, edit secrets", js)
        self.assertIn("Maintenance toolchain", js)
        self.assertIn("Before treating WebView as daily-driver ready, process a small known batch", js)
        self.assertIn("WebView readiness is not proof by itself", js)
        self.assertIn("renderDailyDriverReadiness(dashboardContext)", js)
        self.assertIn("function renderRefreshInProgress(options = {})", app_refresh_js)
        self.assertIn("refreshAll({ queueRefresh: true })", queue_view_js)
        self.assertIn("refreshAll({ automatic: true })", js)
        self.assertIn("const AUTOMATIC_REFRESH_INTERVAL_MS = 15000", js)
        self.assertIn("window.setInterval(() => refreshAll({ automatic: true }), AUTOMATIC_REFRESH_INTERVAL_MS)", js)
        self.assertIn("lastRefreshDurationMs", js)
        self.assertIn(".activity-meta", css_layout)
        self.assertIn("text-overflow: ellipsis", css_split_assets)
        self.assertIn("text-overflow: ellipsis", css_layout)
        self.assertIn(".page-panel-empty-window", css_components)
        self.assertIn(".page-panel-empty-window.is-visible", css_components)
        self.assertIn("this checklist is read-only and does not launch, repair, drain, save, rename, delete, publish, or touch media files", js)
        self.assertIn("settings: values.settings || getLastSettings()", js)
        self.assertIn("[data-cross-page-target]", js)
        self.assertIn("renderNetworkViewFn({", js)
        self.assertIn("window.mediaPipelineReportsView?.renderReports?.(lastSnapshot, getLastSettings())", js)
        self.assertIn("source=markers", js)
        self.assertIn("priority_only=true", js)
        self.assertIn("window.mediaPipelineMaintenanceView?.getLastMaintenance?.()", js)
        self.assertIn("getLastMaintenance", maintenance_view_js)
        self.assertIn("startPipelineFromForm", js)
        self.assertNotIn("startAuditFromForm", js)
        self.assertIn("startRerunFromForm", js)
        self.assertIn("movie_filter_options", rename_view_js)
        self.assertIn("remove_terms_text", rename_view_js)
        self.assertIn("final_name_overrides", rename_view_js)
        self.assertIn("force_pipeline_name_overrides", rename_view_js)
        self.assertIn("applySelectedRename", rename_view_js)
        self.assertIn("renderDiagnostics", js)
        self.assertIn("renderCloseReadiness", js)
        self.assertIn("formatCloseReadiness", js)
        self.assertIn("Watcher generation:", js)
        self.assertIn("diagnostics-close-readiness", js)
        self.assertIn("function renderHomeReadiness", js)
        self.assertIn("function homeReadinessNextStep", js)
        self.assertIn("function renderControlReadiness", js)
        self.assertIn("function pipelineControlReadinessStatus", js)
        self.assertIn("function pipelineControlReadinessLines", js)
        self.assertIn("Mutation guardrail: control buttons send backend-owned control flags through /api/pipeline/control", js)
        self.assertIn("mediaPipelineProgressView?.renderHomeActiveWork?.({", js)
        self.assertIn("Required read failure(s):", js)
        self.assertIn("Supporting read issue(s):", js)
        self.assertIn("Next step:", js)
        self.assertIn("beforeunload", js)
        self.assertIn("closeReadinessRequiresWarning", js)
        self.assertIn("Promise.allSettled", js)
        self.assertIn("renderRefreshHealth", js)
        self.assertIn("refreshFailure", js)
        self.assertIn("requestPipelineControl", js)
        self.assertIn("let refreshInFlight = false", js)
        self.assertIn("let refreshQueued = false", js)
        self.assertIn("async function refreshAllNow(options = {})", js)
        self.assertIn("if (refreshInFlight)", js)
        self.assertIn("if (refreshOptions.automatic) return", js)
        self.assertIn("Refresh failed: ${message}", js)
        self.assertIn('name: "refresh/render"', js)
        self.assertIn("window.setTimeout(() => refreshAll(queuedOptions), 0)", js)
        self.assertIn("formatCommandHistoryTime", command_history_js)
        self.assertIn("formatCommandHistoryLines", command_history_js)
        self.assertIn("issue=${issue}", command_history_js)
        self.assertIn("commandHistoryOwnerPage(item)", command_history_js)
        self.assertIn("const issue = commandHistoryIssueLevel(item)", command_history_js)
        self.assertIn("diagnostics-command-history", command_history_js)
        self.assertIn("function renderDiagnosticsCommandDrilldown", command_history_js)
        self.assertIn("function commandHistoryDiagnosticsDrilldownRows", command_history_js)
        self.assertIn("function commandHistoryDiagnosticsDrilldownSummaryLines", command_history_js)
        self.assertIn("function commandHistoryDiagnosticsEvidenceRows", command_history_js)
        self.assertIn("function commandHistoryOwnerImpactRows", command_history_js)
        self.assertIn("function renderDiagnosticsCommandOwnerImpact", command_history_js)
        self.assertIn("function renderCommandDiagnosticsEvidence", command_history_js)
        self.assertIn("Diagnostics command-result drilldown:", command_history_js)
        self.assertIn("Command owner impact:", command_history_js)
        self.assertIn("Selection behavior: selecting an owner row selects its latest command", command_history_js)
        self.assertIn("Command / diagnostics evidence correlation:", command_history_js)
        self.assertIn("possible related evidence only", command_history_js)
        self.assertIn("Read-first order: command detail -> Last Stderr / Latest Failure -> owning page state.", command_history_js)
        self.assertIn("Mutation guardrail: Diagnostics drilldown is read-only", command_history_js)
        self.assertIn("Guardrail: this correlation cannot prove success/failure by itself", command_history_js)


if __name__ == "__main__":
    unittest.main()
