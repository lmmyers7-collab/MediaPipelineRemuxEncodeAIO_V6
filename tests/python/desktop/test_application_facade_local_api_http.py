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
from mediapipeline.core.failures.cleanup_service import FailureCleanupServiceMixin
from mediapipeline.core.paths.layout import path_within_root
from mediapipeline.desktop.api.handler import build_local_api_handler_class
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from mediapipeline.desktop.local_api_main import BOOTSTRAP_SCHEMA_VERSION, bootstrap_payload, build_backend, main as local_api_main
from mediapipeline.desktop.models import ResolvedPaths, Snapshot
from tests.python.desktop.application_facade_test_support import (
    COMMAND_HISTORY_ASSET_ORDER,
    DummyFacadeService,
    DummyProc,
    DummyWorkflowFacadeService,
    LocalApiHttpTestMixin,
    served_webview_static_contract_bundle,
    assert_namespace_export as _assert_namespace_export,
    _render_static_index_html,
    _resolved,
)


class LocalApiHttpTests(LocalApiHttpTestMixin, unittest.TestCase):
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

    def test_failure_artifacts_route_is_authenticated_read_only_and_not_journaled(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            resolved.config_data = {"FailureArtifactWarningThresholdGB": 0.000001}
            artifacts = resolved.state_root / "Failures" / "Artifacts"
            artifacts.mkdir(parents=True)
            artifact = artifacts / "failed-output.mkv"
            artifact.write_bytes(b"x" * 2048)
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                denied_status, denied = self._get_json(f"{server.url}/api/failures/artifacts")
                status, payload = self._get_json(f"{server.url}/api/failures/artifacts", token="test-token")
                commands_status, commands = self._get_json(f"{server.url}/api/commands?limit=10", token="test-token")
                artifact_size_after = artifact.stat().st_size
            finally:
                server.stop()

        self.assertEqual(denied_status, 401)
        self.assertEqual(denied["error"], "unauthorized")
        self.assertEqual(status, 200)
        self.assertEqual(payload["schema_version"], "failure_artifact_summary.v1")
        self.assertEqual(payload["evidence_authority"], "backend")
        self.assertEqual(payload["total_bytes"], 2048)
        self.assertEqual(payload["file_count"], 1)
        self.assertEqual(payload["largest_files"][0]["name"], "failed-output.mkv")
        self.assertTrue(payload["warning"])
        self.assertEqual(payload["touches_media"], False)
        self.assertEqual(payload["cleanup_route_available"], True)
        self.assertEqual(commands_status, 200)
        self.assertEqual(commands["entries"], [])
        self.assertEqual(artifact_size_after, 2048)

    def test_failure_artifact_cleanup_route_previews_and_deletes_only_confirmed_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved = _resolved(root)
            resolved.local_base = root / "LocalBase"
            resolved.state_root = resolved.local_base / "State"
            resolved.failed_markers_path = resolved.state_root / "Failures" / "Markers"
            resolved.failed_reports_path = resolved.state_root / "Failures" / "Reports"
            resolved.config_data = {"FailureArtifactRetentionDays": 1}
            artifacts = resolved.state_root / "Failures" / "Artifacts"
            artifacts.mkdir(parents=True)
            old_artifact = artifacts / "old-artifact.mkv"
            recent_artifact = artifacts / "recent-artifact.mkv"
            old_artifact.write_bytes(b"x" * 128)
            recent_artifact.write_bytes(b"y" * 256)
            os.utime(old_artifact, (1_700_000_000, 1_700_000_000))
            os.utime(recent_artifact, (int(time.time()), int(time.time())))
            marker = resolved.failed_markers_path / "marker-1.json"
            report = resolved.failed_reports_path / "round_failures_1.json"
            media = root / "Movie.mkv"
            marker.parent.mkdir(parents=True)
            report.parent.mkdir(parents=True)
            marker.write_text("{}", encoding="utf-8")
            report.write_text("[]", encoding="utf-8")
            media.write_bytes(b"media")
            facade = MediaPipelineApplicationFacade(_FailureArtifactCleanupRouteService(root), app_version="v6-test")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                denied_status, denied = self._post_json(
                    f"{server.url}/api/failures/artifacts/cleanup",
                    {"dry_run": True},
                )
                preview_status, preview = self._post_json(
                    f"{server.url}/api/failures/artifacts/cleanup",
                    {"dry_run": True, "confirm_delete": False},
                    token="test-token",
                )
                confirm_status, confirmed = self._post_json(
                    f"{server.url}/api/failures/artifacts/cleanup",
                    {
                        "dry_run": False,
                        "confirm_delete": True,
                    },
                    token="test-token",
                )
                selected_preview_status, selected_preview = self._post_json(
                    f"{server.url}/api/failures/artifacts/cleanup",
                    {
                        "dry_run": True,
                        "confirm_delete": False,
                        "artifact_paths": [str(recent_artifact)],
                    },
                    token="test-token",
                )
                selected_confirm_status, selected_confirmed = self._post_json(
                    f"{server.url}/api/failures/artifacts/cleanup",
                    {
                        "dry_run": False,
                        "confirm_delete": True,
                        "dry_run_fingerprint": selected_preview["data"]["dry_run_fingerprint"],
                        "reason": "operator selected failure artifact",
                        "artifact_paths": [str(recent_artifact)],
                    },
                    token="test-token",
                )
            finally:
                server.stop()

            self.assertFalse(old_artifact.exists())
            self.assertFalse(recent_artifact.exists())
            self.assertTrue(marker.exists())
            self.assertTrue(report.exists())
            self.assertTrue(media.exists())
            manifest_exists = Path(confirmed["data"]["manifest_path"]).exists()
            selected_manifest_exists = Path(selected_confirmed["data"]["manifest_path"]).exists()

        self.assertEqual(denied_status, 401)
        self.assertEqual(denied["error"], "unauthorized")
        self.assertEqual(preview_status, 200)
        self.assertTrue(preview["ok"])
        self.assertTrue(preview["data"]["dry_run"])
        self.assertEqual(preview["data"]["planned_count"], 1)
        self.assertTrue(preview["data"]["dry_run_fingerprint"])
        self.assertEqual(preview["data"]["touches_media"], False)
        self.assertEqual(preview["data"]["source_media_mutation"], False)
        self.assertEqual(confirm_status, 200)
        self.assertTrue(confirmed["ok"])
        self.assertEqual(confirmed["data"]["deleted_count"], 1)
        self.assertEqual(confirmed["data"]["deleted_bytes"], 128)
        self.assertTrue(confirmed["data"]["writes_failure_artifacts"])
        self.assertEqual(confirmed["data"]["confirmation_mode"], "current_plan")
        self.assertEqual(confirmed["data"]["touches_media"], False)
        self.assertEqual(confirmed["data"]["source_media_mutation"], False)
        self.assertTrue(manifest_exists)
        self.assertEqual(selected_preview_status, 200)
        self.assertTrue(selected_preview["ok"])
        self.assertEqual(selected_preview["data"]["planned_count"], 1)
        self.assertEqual(selected_preview["data"]["planned"][0]["name"], "recent-artifact.mkv")
        self.assertEqual(selected_preview["data"]["requested_artifact_paths"], [str(recent_artifact)])
        self.assertTrue(selected_preview["data"]["policy"]["selection_enabled"])
        self.assertEqual(selected_confirm_status, 200)
        self.assertTrue(selected_confirmed["ok"])
        self.assertEqual(selected_confirmed["data"]["deleted_count"], 1)
        self.assertEqual(selected_confirmed["data"]["deleted_bytes"], 256)
        self.assertTrue(selected_confirmed["data"]["writes_failure_artifacts"])
        self.assertEqual(selected_confirmed["data"]["touches_media"], False)
        self.assertEqual(selected_confirmed["data"]["source_media_mutation"], False)
        self.assertTrue(selected_manifest_exists)

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
        self.assertNotIn("long_run_reliability", health)
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
        self.assertIn("/api/failures/artifacts", contract["auth"]["token_routes"])
        self.assertIn("/api/failures/open", contract["auth"]["token_routes"])
        self.assertIn("/api/failures/artifacts/cleanup", contract["auth"]["token_routes"])
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
        self.assertEqual(paths_by_effect["/api/failures/artifacts"], "none")
        self.assertEqual(paths_by_effect["/api/failures/open"], "shell-open")
        self.assertEqual(paths_by_effect["/api/failures/artifacts/cleanup"], "failure-artifact-delete")
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
        self.assertEqual(snapshot["counts"]["long_run_reliability"]["schema_version"], "desktop_runtime_reliability_counters.v1")
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

    def test_completed_route_includes_parked_pending_publish_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            pending_root = root / "PendingServerPush"
            pending_root.mkdir(parents=True)
            parked_file = pending_root / "Cars (2006).mkv"
            parked_file.write_bytes(b"parked-output")
            destination = root / "Final" / "Movies" / "Cars (2006).mkv"
            source = root / "Source" / "Cars (2006).mkv"
            manifest_path = pending_root / "Cars (2006).mkv.manifest.json"
            manifest_path.write_text(
                json.dumps(
                    {
                        "schema_version": "pending_push_manifest.v1",
                        "parked_at": "2026-07-04T23:20:00-04:00",
                        "pipeline_version": "test",
                        "publish_transaction_id": "tx-cars",
                        "manifest_state": "parked",
                        "local_file": str(parked_file),
                        "server_out": str(destination),
                        "route": "remux",
                        "source_identity_v2": "source-id-cars",
                        "source_identity_v2_algorithm": "sha256",
                        "source_path": str(source),
                        "source_size": 4096,
                        "output_size": parked_file.stat().st_size,
                        "publish_mode": "deferred",
                        "sidecar_files": [],
                        "tx3g_srt_tracks": [],
                        "tx3g_srt_failures": [],
                        "bdpgs_srt_failures": [],
                        "vobsub_srt_failures": [],
                        "tx3g_embedded_srt_tracks": [],
                        "bdpgs_embedded_srt_tracks": [],
                        "vobsub_embedded_srt_tracks": [],
                    }
                ),
                encoding="utf-8",
            )
            completed_manifest = root / "State" / "Completed" / "completed_jobs.jsonl"
            completed_manifest.parent.mkdir(parents=True)
            completed_manifest.write_text("", encoding="utf-8")
            resolved = _resolved(root)
            resolved.completed_manifest_path = completed_manifest
            resolved.pending_push_path = pending_root
            facade = MediaPipelineApplicationFacade(DummyWorkflowFacadeService(root), app_version="v6-test")
            server = LocalApiServer(facade, token="test-token", resolved_provider=lambda: resolved)
            try:
                server.start()
                completed_status, completed = self._get_json(
                    f"{server.url}/api/completed",
                    token="test-token",
                )
            finally:
                server.stop()

        self.assertEqual(completed_status, 200)
        self.assertEqual(completed["schema_version"], "desktop_completed_preview.v1")
        self.assertEqual(completed["count"], 1)
        self.assertEqual(completed["completed_pending_proof"]["schema_version"], "desktop_completed_pending_proof.v1")
        row = completed["rows"][0]
        self.assertEqual(row["completed_source"], "pending_publish")
        self.assertEqual(row["publish_state"], "parked")
        self.assertEqual(row["operator_status_state"], "parked")
        self.assertEqual(row["pending_publish_manifest_path"], str(manifest_path))
        self.assertEqual(row["output_path"], str(destination))
        self.assertEqual(row["available_open_targets"], [])


class _FailureArtifactCleanupRouteService(DummyFacadeService, FailureCleanupServiceMixin):
    def _path_within_root(self, path: Path, root: Path) -> bool:
        return path_within_root(path, root)


if __name__ == "__main__":
    unittest.main()
