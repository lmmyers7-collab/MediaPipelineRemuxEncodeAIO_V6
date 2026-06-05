from __future__ import annotations

import io
import json
import logging
import sys
import tempfile
import threading
import unittest
import urllib.error
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.network.auth import AUTH_VERSION
from mediapipeline.desktop.network.cluster_log import format_cluster_log_line
from mediapipeline.desktop.network.coordinator import (
    CoordinatorDispatcher,
    _CoordHandler,
    _coordinator_health_heartbeat_timeout_mins,
)
from mediapipeline.desktop.network.diagnostics import diagnostic_preview
from mediapipeline.desktop.network.firewall import (
    add_firewall_rule,
    build_add_firewall_rule_command,
    check_firewall_port,
    parse_matching_firewall_rule_names,
)
from mediapipeline.desktop.network.http_json import http_get_json, http_post_json
from mediapipeline.desktop.network.identity import (
    LOG_MESSAGE_TRUNCATION_SUFFIX,
    coerce_worker_name,
    is_valid_worker_id,
    sanitize_log_entry_fields,
)
from mediapipeline.desktop.network.coordinator_http import (
    MAX_COORDINATOR_BODY_BYTES,
    parse_query_params,
    validate_content_length,
)
from mediapipeline.desktop.network.coordinator_policy import (
    RETRY_AFTER_ACTIVE_SECONDS,
    RETRY_AFTER_IDLE_SECONDS,
    compute_retry_after_seconds,
    coordinator_bind_address,
    coordinator_port,
    heartbeat_timeout_mins,
)
from mediapipeline.desktop.network.coordinator_url import validate_coordinator_url
from mediapipeline.desktop.network.encode_config_snapshot import snapshot_encode_config
from mediapipeline.desktop.network.failure_policy import source_has_prior_failure
from mediapipeline.desktop.network.path_map import apply_source_path_map, parse_source_path_map
from mediapipeline.desktop.network.poll_policy import resolve_worker_poll_interval, resolve_worker_wait_seconds
from mediapipeline.desktop.network.probe import probe_coordinator_health, probe_worker_auth
from mediapipeline.desktop.network.protocol import ClaimResponse, DoneRequest, HeartbeatRequest, LogEntryRequest
from mediapipeline.desktop.network.registry import InFlightRegistry
from mediapipeline.desktop.network.share_block import (
    coerce_coordinator_port,
    format_coordinator_share_block,
    select_coordinator_share_ip,
)
from mediapipeline.desktop.network.threading_helpers import start_daemon_thread
from mediapipeline.desktop.network.worker_state import atomic_write_text, load_worker_state, save_worker_state
from mediapipeline.desktop.network.worker import (
    WorkerDispatcher,
    _atomic_write_text,
    _http_read_capped,
    _make_queue_record,
    _safe_hostname,
    _validate_coordinator_url,
)
from mediapipeline.desktop.network.worker_done import (
    build_completion_done_request,
    build_crash_recovery_done_request,
    build_release_done_request,
)
from mediapipeline.desktop.network.worker_record import make_queue_record


class NetworkCoordinatorHelperTests(unittest.TestCase):
    def test_coordinator_url_helper_stays_compatible_with_worker_alias(self) -> None:
        self.assertEqual(validate_coordinator_url(" http://host:7830/ "), "http://host:7830")
        self.assertIs(validate_coordinator_url, _validate_coordinator_url)

    def test_share_block_formats_operator_connection_details(self) -> None:
        self.assertEqual(coerce_coordinator_port("not-a-port"), 7830)
        self.assertEqual(coerce_coordinator_port("70000"), 7830)
        self.assertEqual(coerce_coordinator_port("0"), 7830)
        self.assertEqual(select_coordinator_share_ip("0.0.0.0", "192.168.1.20", ["10.0.0.5"]), "192.168.1.20")
        self.assertEqual(select_coordinator_share_ip("127.0.0.1", "192.168.1.20", []), "127.0.0.1")

        block = format_coordinator_share_block(
            port="9000",
            token="secret-token",
            bind_address="0.0.0.0",
            primary_ip="192.168.1.20",
            detected_ips=[],
        )

        self.assertEqual(block, "Coordinator URL: http://192.168.1.20:9000\nAuth Token:      secret-token")

    def test_network_probe_helpers_check_health_and_worker_auth(self) -> None:
        class FakeResponse:
            def __init__(self, code: int) -> None:
                self.code = code

            def __enter__(self):
                return self

            def __exit__(self, *_args) -> bool:
                return False

            def getcode(self) -> int:
                return self.code

        requests: list[object] = []

        def fake_urlopen(request, timeout: int):
            requests.append((request, timeout))
            return FakeResponse(200)

        with patch("mediapipeline.desktop.network.probe.urllib.request.urlopen", side_effect=fake_urlopen):
            health = probe_coordinator_health("http://coordinator:7830/")
            auth = probe_worker_auth("http://coordinator:7830/", "token")

        health_request, health_timeout = requests[0]
        auth_request, auth_timeout = requests[1]
        self.assertTrue(health.ok)
        self.assertEqual(health.detail, "HTTP 200")
        self.assertEqual(health_request, "http://coordinator:7830/api/health")
        self.assertEqual(health_timeout, 4)
        self.assertTrue(auth.ok)
        self.assertEqual(auth.detail, "Token accepted (HTTP 200)")
        self.assertEqual(auth_request.full_url, "http://coordinator:7830/api/workers")
        auth_headers = {key.casefold(): value for key, value in auth_request.header_items()}
        self.assertNotIn("authorization", auth_headers)
        self.assertEqual(auth_headers["x-mediapipeline-auth-version"], AUTH_VERSION)
        self.assertIn("x-mediapipeline-signature", auth_headers)
        self.assertEqual(auth_timeout, 4)

    def test_coordinator_health_probe_normalizes_failure_details(self) -> None:
        with patch(
            "mediapipeline.desktop.network.probe.urllib.request.urlopen",
            side_effect=TimeoutError("connection timed out while connecting"),
        ):
            timeout = probe_coordinator_health("http://coordinator:7830/")

        self.assertFalse(timeout.ok)
        self.assertIsNone(timeout.status_code)
        self.assertEqual(timeout.detail, "Cannot reach http://coordinator:7830/api/health")

        http_error = urllib.error.HTTPError(
            "http://coordinator:7830/api/health",
            503,
            "Service Unavailable",
            hdrs=None,
            fp=None,
        )
        with patch("mediapipeline.desktop.network.probe.urllib.request.urlopen", side_effect=http_error):
            unavailable = probe_coordinator_health("http://coordinator:7830/")

        self.assertFalse(unavailable.ok)
        self.assertEqual(unavailable.status_code, 503)
        self.assertEqual(unavailable.detail, "HTTP 503")

    def test_worker_auth_probe_normalizes_failure_details(self) -> None:
        unauthorized_error = urllib.error.HTTPError(
            "http://coordinator:7830/api/workers",
            401,
            "Unauthorized",
            hdrs=None,
            fp=None,
        )
        with patch("mediapipeline.desktop.network.probe.urllib.request.urlopen", side_effect=unauthorized_error):
            unauthorized = probe_worker_auth("http://coordinator:7830/", "bad-token")

        self.assertFalse(unauthorized.ok)
        self.assertEqual(unauthorized.status_code, 401)
        self.assertEqual(unauthorized.detail, "401 Unauthorized - token does not match coordinator")

        forbidden_error = urllib.error.HTTPError(
            "http://coordinator:7830/api/workers",
            403,
            "Forbidden",
            hdrs=None,
            fp=None,
        )
        with patch("mediapipeline.desktop.network.probe.urllib.request.urlopen", side_effect=forbidden_error):
            forbidden = probe_worker_auth("http://coordinator:7830/", "token")

        self.assertFalse(forbidden.ok)
        self.assertEqual(forbidden.status_code, 403)
        self.assertEqual(forbidden.detail, "HTTP 403")

        with patch(
            "mediapipeline.desktop.network.probe.urllib.request.urlopen",
            side_effect=ConnectionRefusedError("connection refused"),
        ):
            refused = probe_worker_auth("http://coordinator:7830/", "token")

        self.assertFalse(refused.ok)
        self.assertIsNone(refused.status_code)
        self.assertEqual(refused.detail, "Cannot reach http://coordinator:7830")

    def test_coordinator_http_helpers_parse_query_and_validate_body_length(self) -> None:
        self.assertEqual(
            parse_query_params("/api/claim?worker_id=worker+1&empty&path=C%3A%5CMedia"),
            {"worker_id": "worker 1", "empty": "", "path": r"C:\Media"},
        )

        ok = validate_content_length("12")
        malformed = validate_content_length("not-int")
        negative = validate_content_length("-1")
        oversized = validate_content_length(str(MAX_COORDINATOR_BODY_BYTES + 1))

        self.assertTrue(ok.ok)
        self.assertEqual(ok.length, 12)
        self.assertFalse(malformed.ok)
        self.assertEqual(malformed.status, 400)
        self.assertFalse(negative.ok)
        self.assertEqual(negative.status, 400)
        self.assertFalse(oversized.ok)
        self.assertEqual(oversized.status, 413)
        self.assertTrue(oversized.close_connection)

    def test_coordinator_policy_helpers_coerce_config_and_retry_hints(self) -> None:
        self.assertEqual(coordinator_port({"CoordinatorPort": "9000"}), 9000)
        self.assertEqual(coordinator_port({}), 7830)
        self.assertEqual(coordinator_port({"CoordinatorPort": "not-a-port"}), 7830)
        self.assertEqual(coordinator_port({"CoordinatorPort": 0}), 7830)
        self.assertEqual(coordinator_port({"CoordinatorPort": 70000}), 7830)
        self.assertEqual(coordinator_bind_address({"CoordinatorBindAddress": "127.0.0.1"}), "127.0.0.1")
        self.assertEqual(coordinator_bind_address({"CoordinatorBindAddress": "http://0.0.0.0"}), "0.0.0.0")
        self.assertEqual(heartbeat_timeout_mins({"CoordinatorHeartbeatTimeoutMins": "0.5"}), 0.5)
        self.assertEqual(heartbeat_timeout_mins({"CoordinatorHeartbeatTimeoutMins": "not-a-number"}), 5.0)
        self.assertEqual(heartbeat_timeout_mins({"CoordinatorHeartbeatTimeoutMins": -1}), 5.0)
        self.assertEqual(heartbeat_timeout_mins({"CoordinatorHeartbeatTimeoutMins": "nan"}), 5.0)
        self.assertEqual(heartbeat_timeout_mins({"CoordinatorHeartbeatTimeoutMins": "inf"}), 5.0)
        self.assertEqual(compute_retry_after_seconds(1), RETRY_AFTER_ACTIVE_SECONDS)
        self.assertEqual(compute_retry_after_seconds(0), RETRY_AFTER_IDLE_SECONDS)
        with self.assertLogs("mediapipeline.desktop.network.coordinator_policy", level="WARNING") as logs:
            self.assertEqual(compute_retry_after_seconds(object()), RETRY_AFTER_IDLE_SECONDS)
        self.assertIn("Invalid active_count", "\n".join(logs.output))

    def test_coordinator_health_heartbeat_timeout_fallback_is_logged(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._heartbeat_timeout_mins = lambda: (_ for _ in ()).throw(RuntimeError("config unavailable"))  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            self.assertEqual(_coordinator_health_heartbeat_timeout_mins(dispatcher), 5.0)

        self.assertIn("Coordinator health heartbeat timeout lookup failed", "\n".join(logs.output))
        self.assertIn("config unavailable", "\n".join(logs.output))

    def test_coordinator_reaper_interval_fallback_is_logged(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._heartbeat_timeout_mins = lambda: (_ for _ in ()).throw(RuntimeError("config unavailable"))  # type: ignore[method-assign]

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            self.assertEqual(CoordinatorDispatcher._reaper_interval_seconds(dispatcher), 60.0)

        self.assertIn("Coordinator reaper heartbeat timeout lookup failed", "\n".join(logs.output))
        self.assertIn("config unavailable", "\n".join(logs.output))

    def test_encode_config_snapshot_applies_case_insensitive_worker_overrides(self) -> None:
        config = {
            "VideoCodec": "hevc_nvenc",
            "VideoPreset": "p4",
            "SizeGuardMode": "strict",
            "UnrelatedKey": "ignored",
            "WorkerConfigOverrides": json.dumps(
                {
                    "BEAST-PC": {
                        "VideoPreset": "p7",
                        "ExtraVideoFlags": "-b:v 8M",
                        "SourceMovies": r"\\server\source",
                        "WorkerAuthToken": "do-not-send",
                    }
                }
            ),
        }

        with self.assertLogs("mediapipeline.desktop.network.encode_config_snapshot", level="WARNING") as logs:
            snapshot = snapshot_encode_config(config, "beast-pc")

        self.assertEqual(snapshot["VideoCodec"], "hevc_nvenc")
        self.assertEqual(snapshot["VideoPreset"], "p7")
        self.assertEqual(snapshot["SizeGuardMode"], "strict")
        self.assertEqual(snapshot["ExtraVideoFlags"], "-b:v 8M")
        self.assertNotIn("UnrelatedKey", snapshot)
        self.assertNotIn("SourceMovies", snapshot)
        self.assertNotIn("WorkerAuthToken", snapshot)
        self.assertIn("Ignoring unsupported WorkerConfigOverrides keys", "\n".join(logs.output))

    def test_coordinator_snapshot_encode_config_uses_helper(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._app = SimpleNamespace(
            resolved=SimpleNamespace(
                config_data={
                    "VideoCodec": "h264_nvenc",
                    "WorkerConfigOverrides": json.dumps({"worker-a": {"VideoCodec": "hevc_nvenc"}}),
                }
            )
        )

        snapshot = CoordinatorDispatcher._snapshot_encode_config(dispatcher, "WORKER-A")

        self.assertEqual(snapshot["VideoCodec"], "hevc_nvenc")

    def test_prior_failure_policy_matches_source_case_insensitively(self) -> None:
        records = [
            SimpleNamespace(source_path_text=r"\\SERVER\Media\Movie.mkv"),
            SimpleNamespace(source_path_text=""),
            object(),
        ]

        self.assertTrue(source_has_prior_failure(r"\\server\media\movie.mkv", records))
        self.assertFalse(source_has_prior_failure(r"\\server\media\other.mkv", records))

    def test_prior_failure_policy_logs_uninspectable_records(self) -> None:
        class BrokenRecord:
            @property
            def source_path_text(self) -> str:
                raise RuntimeError("bad record")

        with self.assertLogs("mediapipeline.desktop.network.failure_policy", level="WARNING") as logs:
            self.assertFalse(source_has_prior_failure(r"C:\Media\Movie.mkv", [BrokenRecord()]))

        self.assertIn("Could not inspect prior failure record", "\n".join(logs.output))

    def test_coordinator_prior_failure_wrapper_uses_app_records(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._app = SimpleNamespace(failure_records=[SimpleNamespace(source_path_text=r"C:\Media\Failed.mkv")])

        self.assertTrue(CoordinatorDispatcher._source_has_prior_failure(dispatcher, r"c:\media\failed.mkv"))



if __name__ == "__main__":
    unittest.main()
