from __future__ import annotations

import io
import json
import logging
import sys
import tempfile
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.api.command_journal import CommandJournal
from mediapipeline.desktop.api.contract import LOCAL_API_ROUTE_CONTRACT
from mediapipeline.desktop.api.http_helpers import (
    LOCAL_API_CONTENT_SECURITY_POLICY,
    content_type_for,
    host_header_authorized,
    no_token_dev_allowed,
    origin_header_authorized,
    query_bool,
    query_int,
    query_value,
    read_json_body,
    request_authorized,
    resolve_asset_path,
    send_bytes,
)
from mediapipeline.desktop.api.routes import GET_ROUTE_HANDLERS, POST_ROUTE_HANDLERS
from mediapipeline.desktop.api.static_files import local_api_bootstrap, read_static_asset, render_index
from mediapipeline.desktop.application import CommandResult, MediaPipelineApplicationFacade
from mediapipeline.desktop.models import ResolvedPaths
from tests.python.desktop.test_application_facade import DummyFacadeService


class ApplicationFacadeCoreContractTests(unittest.TestCase):
    def test_command_result_serializes_consistently(self) -> None:
        result = CommandResult(
            command="refresh",
            ok=True,
            message="Refreshed.",
            refresh_hint="snapshot",
            log_paths={"stdout": "stdout.log"},
        )

        mapping = result.to_mapping()

        self.assertEqual(mapping["schema_version"], "desktop_command_result.v1")
        self.assertTrue(mapping["ok"])
        self.assertEqual(mapping["command"], "refresh")
        self.assertEqual(mapping["log_paths"]["stdout"], "stdout.log")

    def test_command_result_mapping_replaces_nonfinite_numbers_for_strict_json(self) -> None:
        result = CommandResult(
            command="telemetry.probe",
            ok=True,
            message="Collected telemetry.",
            data={
                "cpu_percent": float("nan"),
                "samples": [1.0, float("inf"), float("-inf")],
            },
        )

        mapping = result.to_mapping()

        self.assertIsNone(mapping["data"]["cpu_percent"])
        self.assertEqual(mapping["data"]["samples"], [1.0, None, None])
        json.dumps(mapping, ensure_ascii=False, sort_keys=True, allow_nan=False)

    def test_runtime_outcome_helper_normalizes_completion_and_failure_events(self) -> None:
        from mediapipeline.core.observability.runtime_outcomes import runtime_outcome_from_event, runtime_outcome_index, source_identity_key

        source = r"C:\Media\Source\Movie.mkv"
        job_completed = {
            "schema_version": "pipeline_event.v1",
            "event_id": "evt-job",
            "event_type": "job_completed",
            "timestamp": "2999-01-01T00:00:00Z",
            "created_at": "2999-01-01T00:00:00Z",
            "stage": "publish",
            "route": "remux",
            "status": "failed",
            "source_path": source,
            "data": {
                "success": False,
                "queue_terminal": False,
                "retryable": True,
                "reason": "Destination rejected the publish.",
                "error_code": "OUTPUT_DESTINATION_LOW_SPACE",
                "publish_state": "park_failed",
                "publish_mode": "deferred",
                "output_path": r"C:\Out\Movie.mkv",
                "output_size_bytes": "4096",
            },
        }
        failure_recorded = {
            "schema_version": "pipeline_event.v1",
            "event_id": "evt-failure",
            "event_type": "failure_recorded",
            "timestamp": "2999-01-01T00:01:00Z",
            "created_at": "2999-01-01T00:01:00Z",
            "stage": "subtitle-ocr",
            "status": "operator_required",
            "data": {
                "source_path": r"C:\Media\Source\Movie2.mkv",
                "reason": "BDPGS OCR failed.",
                "error_code": "SUBTITLE_BDPGS_OCR_FAILED",
            },
        }

        completed = runtime_outcome_from_event(job_completed)
        failure = runtime_outcome_from_event(failure_recorded)
        index = runtime_outcome_index([job_completed, failure_recorded, {"event_type": "tool_completed"}])

        self.assertIsNotNone(completed)
        assert completed is not None
        self.assertEqual(completed["runtime_outcome_status"], "failed")
        self.assertFalse(completed["runtime_outcome_success"])
        self.assertFalse(completed["runtime_outcome_queue_terminal"])
        self.assertTrue(completed["runtime_outcome_retryable"])
        self.assertEqual(completed["runtime_outcome_error_code"], "OUTPUT_DESTINATION_LOW_SPACE")
        self.assertEqual(completed["runtime_outcome_output_size_bytes"], 4096)
        self.assertEqual(completed["runtime_outcome_freshness_status"], "fresh")
        self.assertIsNotNone(failure)
        assert failure is not None
        self.assertEqual(failure["runtime_outcome_status"], "operator_required_failure")
        self.assertEqual(failure["runtime_outcome_source_path"], r"C:\Media\Source\Movie2.mkv")
        self.assertEqual(failure["runtime_outcome_error_code"], "SUBTITLE_BDPGS_OCR_FAILED")
        self.assertIn(source_identity_key(source), index)
        self.assertIn(source_identity_key(r"C:\Media\Source\Movie2.mkv"), index)

    def test_command_journal_persists_bounded_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "RunLogs" / "local_api_command_history.json"
            journal = CommandJournal(path=path, max_entries=2)
            journal.record(
                {
                    "schema_version": "desktop_command_result.v1",
                    "command": "settings.preview_patch",
                    "ok": True,
                    "severity": "info",
                    "message": "x" * 2500,
                    "warnings": ["w1", "w2"],
                    "errors": [],
                    "data": {"large": "not persisted in summary"},
                }
            )
            journal.record(
                {
                    "schema_version": "desktop_command_result.v1",
                    "command": "pipeline.start",
                    "ok": False,
                    "severity": "warning",
                    "message": "blocked by schedule",
                    "warnings": ["outside schedule"],
                    "errors": ["schedule"],
                    "data": {"mode": "once", "secret_token": "hidden"},
                },
                request={"mode": "once", "authorization": "Bearer hidden"},
            )
            journal.record(
                {
                    "schema_version": "desktop_command_result.v1",
                    "command": "rerun.start",
                    "ok": True,
                    "severity": "info",
                    "message": "started",
                }
            )
            journal.record({"schema_version": "not_a_command_result.v1", "command": "ignored"})

            payload = journal.to_mapping(limit=10)
            reloaded = CommandJournal(path=path, max_entries=2).to_mapping(limit=10)
            leftovers = list(path.parent.glob("*.tmp"))

        self.assertEqual(payload["schema_version"], "desktop_command_history.v1")
        self.assertEqual(payload["count"], 2)
        self.assertEqual([entry["command"] for entry in payload["entries"]], ["rerun.start", "pipeline.start"])
        self.assertEqual(payload["entries"][1]["data"]["mode"], "once")
        self.assertEqual(payload["entries"][1]["data"]["secret_token"], "<redacted>")
        self.assertEqual(payload["entries"][1]["request"]["mode"], "once")
        self.assertEqual(payload["entries"][1]["request"]["authorization"], "<redacted>")
        self.assertEqual(reloaded["entries"], payload["entries"])
        self.assertEqual(leftovers, [])

    def test_command_journal_logs_temp_cleanup_failure_after_save_failure(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "RunLogs" / "local_api_command_history.json"
            logger_name = "test.command_journal.cleanup"
            journal = CommandJournal(path=path, max_entries=2, logger=logging.getLogger(logger_name))

            with (
                patch("mediapipeline.desktop.api.command_journal.os.replace", side_effect=OSError("replace denied")),
                patch("pathlib.Path.unlink", side_effect=OSError("cleanup denied")),
                self.assertLogs(logger_name, level="WARNING") as logs,
            ):
                journal.record(
                    {
                        "schema_version": "desktop_command_result.v1",
                        "command": "pipeline.start",
                        "ok": False,
                        "severity": "warning",
                        "message": "blocked",
                    }
                )

        combined = "\n".join(logs.output)
        self.assertIn("Could not remove temporary local API command journal", combined)
        self.assertIn("cleanup denied", combined)
        self.assertIn("Could not save local API command journal", combined)
        self.assertIn("replace denied", combined)

    def test_command_journal_rejects_nonfinite_json_and_cleans_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "RunLogs" / "local_api_command_history.json"
            logger_name = "test.command_journal.strict_json"
            journal = CommandJournal(path=path, max_entries=2, logger=logging.getLogger(logger_name))
            journal._entries = [  # type: ignore[attr-defined]
                {
                    "at": "2026-05-09T00:00:00+00:00",
                    "command": "pipeline.start",
                    "ok": True,
                    "severity": "info",
                    "message": float("nan"),
                    "job_id": "",
                    "refresh_hint": "",
                    "warnings": [],
                    "errors": [],
                    "log_paths": {},
                }
            ]

            with self.assertLogs(logger_name, level="WARNING") as logs:
                journal._save_locked()  # type: ignore[attr-defined]

            leftovers = list(path.parent.glob("*.tmp"))

        combined = "\n".join(logs.output)
        self.assertIn("Could not save local API command journal", combined)
        self.assertIn("Out of range float values", combined)
        self.assertEqual(leftovers, [])

    def test_local_api_http_helpers_guard_auth_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            assets = root / "assets"
            assets.mkdir()
            script = assets / "app.js"
            script.write_text("console.log('ok');", encoding="utf-8")

            allowed = resolve_asset_path(root, "/assets/app.js")
            traversal = resolve_asset_path(root, "/assets/../secret.txt")
            backslash = resolve_asset_path(root, "/assets/..\\secret.txt")

        self.assertEqual(allowed, script)
        self.assertIsNone(traversal)
        self.assertIsNone(backslash)
        self.assertEqual(content_type_for(Path("app.js")), "text/javascript; charset=utf-8")
        self.assertTrue(request_authorized({}, {}, token="secret", require_token=False))
        self.assertTrue(request_authorized({"Authorization": "Bearer secret"}, {}, token="secret", require_token=True))
        self.assertTrue(request_authorized({"X-MediaPipeline-Token": "secret"}, {}, token="secret", require_token=True))
        self.assertFalse(request_authorized({}, {"token": ["secret"]}, token="secret", require_token=True))
        self.assertFalse(request_authorized({"Authorization": "Bearer wrong"}, {}, token="secret", require_token=True))
        self.assertTrue(host_header_authorized("127.0.0.1:8765", bind_host="127.0.0.1", port=8765))
        self.assertTrue(host_header_authorized("localhost:8765", bind_host="127.0.0.1", port=8765))
        self.assertFalse(host_header_authorized("evil.example:8765", bind_host="127.0.0.1", port=8765))
        self.assertFalse(host_header_authorized("127.0.0.1:9999", bind_host="127.0.0.1", port=8765))
        self.assertTrue(
            origin_header_authorized(
                "http://127.0.0.1:8765",
                bind_host="127.0.0.1",
                port=8765,
            )
        )
        self.assertFalse(
            origin_header_authorized(
                "https://127.0.0.1:8765",
                bind_host="127.0.0.1",
                port=8765,
            )
        )
        self.assertFalse(
            origin_header_authorized(
                "http://evil.example:8765",
                bind_host="127.0.0.1",
                port=8765,
            )
        )
        self.assertTrue(no_token_dev_allowed("127.0.0.1", environ={"MEDIAPIPELINE_ALLOW_NO_TOKEN_DEV": "1"}))
        self.assertFalse(no_token_dev_allowed("0.0.0.0", environ={"MEDIAPIPELINE_ALLOW_NO_TOKEN_DEV": "1"}))
        self.assertFalse(no_token_dev_allowed("127.0.0.1", environ={}))
        self.assertEqual(query_value({"source": ["latest_csv"]}, "source", "latest_json"), "latest_csv")
        self.assertEqual(query_value({}, "source", "latest_json"), "latest_json")
        self.assertEqual(query_int({"limit": ["25"]}, "limit", 100), 25)
        self.assertEqual(query_int({"limit": ["bad"]}, "limit", 100), 100)
        self.assertTrue(query_bool({"priority_only": ["yes"]}, "priority_only"))
        self.assertFalse(query_bool({"priority_only": ["0"]}, "priority_only"))

    def test_local_api_send_bytes_adds_security_headers(self) -> None:
        class FakeHandler:
            def __init__(self) -> None:
                self.status: int | None = None
                self.headers: list[tuple[str, str]] = []
                self.ended = False
                self.wfile = io.BytesIO()

            def send_response(self, status: int) -> None:
                self.status = status

            def send_header(self, name: str, value: str) -> None:
                self.headers.append((name, value))

            def end_headers(self) -> None:
                self.ended = True

        handler = FakeHandler()

        send_bytes(handler, b"ok", content_type="text/plain; charset=utf-8")  # type: ignore[arg-type]

        headers = dict(handler.headers)
        self.assertEqual(handler.status, 200)
        self.assertTrue(handler.ended)
        self.assertEqual(handler.wfile.getvalue(), b"ok")
        self.assertEqual(headers["Content-Security-Policy"], LOCAL_API_CONTENT_SECURITY_POLICY)
        self.assertIn("default-src 'self'", headers["Content-Security-Policy"])
        self.assertIn("object-src 'none'", headers["Content-Security-Policy"])
        self.assertEqual(headers["X-Content-Type-Options"], "nosniff")
        self.assertEqual(headers["Referrer-Policy"], "no-referrer")

    def test_local_api_json_body_rejects_nonfinite_constants(self) -> None:
        body = b'{"progress": NaN}'
        sent: list[tuple[dict[str, object], int]] = []
        handler = type(
            "Handler",
            (),
            {
                "headers": {"Content-Length": str(len(body)), "Content-Type": "application/json"},
                "rfile": io.BytesIO(body),
            },
        )()

        result = read_json_body(handler, lambda payload, status: sent.append((payload, status)))

        self.assertIsNone(result)
        self.assertEqual(sent[0][1], 400)
        self.assertIn("non-finite JSON value is not allowed", str(sent[0][0]["error"]))

    def test_local_api_static_file_helpers_render_bootstrap_and_assets(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            assets = root / "assets"
            assets.mkdir()
            (root / "index.html").write_text(
                "window.MEDIA_PIPELINE_BOOTSTRAP = __MEDIA_PIPELINE_BOOTSTRAP__;",
                encoding="utf-8",
            )
            (assets / "app.js").write_text("console.log('ok');", encoding="utf-8")

            bootstrap = local_api_bootstrap(token="secret-token", require_token=True, app_version="v5-test")
            index_response = render_index(root, bootstrap)
            asset_response = read_static_asset(root, "/assets/app.js")
            missing_response = read_static_asset(root, "/assets/../secret.txt")

        self.assertEqual(index_response.status, 200)
        self.assertIn(b"secret-token", index_response.body)
        self.assertIn(b"v5-test", index_response.body)
        self.assertEqual(asset_response.content_type, "text/javascript; charset=utf-8")
        self.assertIn(b"console.log", asset_response.body)
        self.assertEqual(missing_response.status, 404)

    def test_local_api_route_maps_cover_documented_api_contract(self) -> None:
        documented_get = {
            str(route["path"])
            for route in LOCAL_API_ROUTE_CONTRACT
            if route.get("method") == "GET" and route.get("path") != "/api/health"
        }
        documented_post = {
            str(route["path"])
            for route in LOCAL_API_ROUTE_CONTRACT
            if route.get("method") == "POST"
        }
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v5-test")
            server = LocalApiServer(facade)

        self.assertEqual(set(GET_ROUTE_HANDLERS), documented_get)
        self.assertEqual(set(POST_ROUTE_HANDLERS), documented_post)
        for spec in [*GET_ROUTE_HANDLERS.values(), *POST_ROUTE_HANDLERS.values()]:
            self.assertTrue(callable(getattr(server, spec.method_name, None)), spec.method_name)

    def test_ui_preferences_round_trip_uses_state_root_and_allowlisted_keys(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            state_root = root / "State"
            resolved = ResolvedPaths(
                app_root=root,
                workspace_root=root,
                pipeline_path=root / "pipeline.ps1",
                config_path=root / "config.psd1",
                audit_script_path=root / "audit.ps1",
                rerun_script_path=root / "rerun.ps1",
                powershell_host=str(root / "pwsh.exe"),
                state_root=state_root,
            )
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v5-test")
            server = LocalApiServer(facade, resolved_provider=lambda: resolved)

            saved = server._ui_preferences_save_payload(
                {
                    "source_surface": "webview",
                    "storage": {
                        "mediapipeline-layout-v1": "{\"home\":{}}",
                        "mediapipeline-theme": "dark",
                        "not-owned": "ignored",
                    },
                }
            )
            loaded = server._ui_preferences_payload()

        self.assertTrue(saved["ok"])
        self.assertEqual(saved["schema_version"], "desktop_ui_preferences.v1")
        self.assertEqual(saved["source_surface"], "webview")
        self.assertEqual(loaded["storage"]["mediapipeline-layout-v1"], "{\"home\":{}}")
        self.assertEqual(loaded["storage"]["mediapipeline-theme"], "dark")
        self.assertNotIn("not-owned", loaded["storage"])

    def test_ui_preferences_write_permission_error_returns_safe_payload(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            state_root = root / "State"
            resolved = ResolvedPaths(
                app_root=root,
                workspace_root=root,
                pipeline_path=root / "pipeline.ps1",
                config_path=root / "config.psd1",
                audit_script_path=root / "audit.ps1",
                rerun_script_path=root / "rerun.ps1",
                powershell_host=str(root / "pwsh.exe"),
                state_root=state_root,
            )
            facade = MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v5-test")
            server = LocalApiServer(facade, resolved_provider=lambda: resolved)

            with patch(
                "mediapipeline.core.api.commands_ui_preferences.write_ui_preferences",
                side_effect=PermissionError(5, "Access is denied"),
            ):
                payload = server._ui_preferences_save_payload(
                    {
                        "source_surface": "tauri",
                        "storage": {"mediapipeline-theme": "light"},
                    }
                )

        self.assertFalse(payload["ok"])
        self.assertEqual(payload["schema_version"], "desktop_ui_preferences.v1")
        self.assertEqual(payload["source"], "write_failed")
        self.assertEqual(payload["storage"], {})
        self.assertIn("could not write state file", payload["message"])
        self.assertIn("PermissionError", payload["message"])


if __name__ == "__main__":
    unittest.main()

