from __future__ import annotations

import io
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.network.auth import validate_header
from mediapipeline_desktop_app.network.coordinator import CoordinatorDispatcher, _CoordHandler
from mediapipeline_desktop_app.network.identity import (
    LOG_MESSAGE_TRUNCATION_SUFFIX,
    coerce_worker_name,
    is_valid_worker_id,
    sanitize_log_entry_fields,
)
from mediapipeline_desktop_app.network.protocol import LogEntryRequest
from mediapipeline_desktop_app.network.registry import InFlightRegistry
from mediapipeline_desktop_app.network.worker import (
    _http_read_capped,
    _safe_hostname,
    _validate_coordinator_url,
)

class NetworkSecurityTests(unittest.TestCase):
    """Coverage for the N1/N2/N3/N4/N5/N7/N10/N13/N15/N17 fixes."""

    # ------------------------------------------------------------------
    # N1 + N7 — auth token must not bypass on empty / blank
    # ------------------------------------------------------------------
    def test_validate_header_rejects_when_expected_token_is_empty(self) -> None:
        # N1 — used to return True (bypass); now must return False so a
        # cleared token doesn't open the API to anonymous callers.
        self.assertFalse(validate_header({"Authorization": "Bearer x"}, ""))
        self.assertFalse(validate_header({"Authorization": "Bearer x"}, "   "))

    def test_validate_header_accepts_correct_bearer_token(self) -> None:
        token = "a" * 32
        self.assertTrue(validate_header({"Authorization": f"Bearer {token}"}, token))
        self.assertFalse(validate_header({"Authorization": "Bearer other"}, token))
        self.assertFalse(validate_header({}, token))

    def test_validate_header_handles_uppercase_authorization(self) -> None:
        token = "b" * 32
        self.assertTrue(validate_header({"AUTHORIZATION": f"Bearer {token}"}, token))

    def test_update_auth_token_rejects_blank_and_persists(self) -> None:
        saved: list[dict] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._auth_token = "old-token"
        dispatcher._app = SimpleNamespace(
            service=SimpleNamespace(save_app_state=lambda d: saved.append(dict(d))),
        )
        dispatcher.log_cluster_event = lambda **_kwargs: None  # type: ignore[assignment]

        # N7 — empty / whitespace must raise so the UI can surface it.
        with self.assertRaises(ValueError):
            CoordinatorDispatcher.update_auth_token(dispatcher, "")
        with self.assertRaises(ValueError):
            CoordinatorDispatcher.update_auth_token(dispatcher, "   ")
        # Token unchanged on rejection.
        self.assertEqual(dispatcher._auth_token, "old-token")
        # Too-short tokens are also rejected.
        with self.assertRaises(ValueError):
            CoordinatorDispatcher.update_auth_token(dispatcher, "short")

        # Successful rotation persists to app_state.
        new_token = "x" * 32
        CoordinatorDispatcher.update_auth_token(dispatcher, new_token)
        self.assertEqual(dispatcher._auth_token, new_token)
        self.assertEqual(saved, [{"coordinator_auth_token": new_token}])

    def test_rotated_auth_token_persistence_failure_is_not_logged_as_persisted(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._auth_token = "old-token"
        dispatcher._app = SimpleNamespace(
            service=SimpleNamespace(
                save_app_state=lambda _data: (_ for _ in ()).throw(RuntimeError("disk read-only"))
            ),
        )
        dispatcher.log_cluster_event = lambda **_kwargs: None  # type: ignore[assignment]

        with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher.update_auth_token(dispatcher, "x" * 32)

        log_text = "\n".join(logs.output)
        self.assertIn("Could not persist rotated coordinator token", log_text)
        self.assertIn("updated live, but persistence failed", log_text)
        self.assertNotIn("updated and persisted", log_text)

    def test_update_auth_token_cluster_log_failure_does_not_block_rotation(self) -> None:
        saved: list[dict] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._auth_token = "old-token"
        dispatcher._app = SimpleNamespace(
            service=SimpleNamespace(save_app_state=lambda data: saved.append(dict(data))),
        )
        dispatcher.log_cluster_event = lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("cluster blocked"))  # type: ignore[assignment]
        new_token = "x" * 32

        with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="WARNING") as logs:
            CoordinatorDispatcher.update_auth_token(dispatcher, new_token)

        self.assertEqual(dispatcher._auth_token, new_token)
        self.assertEqual(saved, [{"coordinator_auth_token": new_token}])
        output = "\n".join(logs.output)
        self.assertIn("Failed to emit auth-token-rotated cluster event", output)
        self.assertIn("cluster blocked", output)

    def test_generated_auth_token_persistence_failure_is_not_logged_as_stored(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._config = lambda: {}  # type: ignore[assignment]
        dispatcher._app = SimpleNamespace(
            service=SimpleNamespace(
                load_app_state=lambda: {},
                save_app_state=lambda _data: (_ for _ in ()).throw(RuntimeError("disk read-only")),
            ),
        )

        with patch("mediapipeline_desktop_app.network.coordinator.generate_token", return_value="generated-token-123456"):
            with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="WARNING") as logs:
                token = CoordinatorDispatcher._load_or_generate_token(dispatcher)

        self.assertEqual(token, "generated-token-123456")
        log_text = "\n".join(logs.output)
        self.assertIn("Could not persist new coordinator token", log_text)
        self.assertIn("active for this run only", log_text)
        self.assertNotIn("stored in app state", log_text)

    # ------------------------------------------------------------------
    # N2 + N3 — registry rejects mismatched worker_id on complete/unclaim
    # ------------------------------------------------------------------
    def test_registry_complete_rejects_foreign_worker(self) -> None:
        reg = InFlightRegistry()
        reg.claim(
            job_id="j1", worker_id="alice", worker_name="alice-pc",
            source_path=r"\\share\movie.mkv", encode_config={},
        )
        # N2 — foreign worker_id must NOT close someone else's job.
        rejected = reg.complete("j1", "mallory", success=True)
        self.assertIsNone(rejected)
        # Job must still be claimed by the original owner.
        self.assertTrue(reg.is_in_flight(r"\\share\movie.mkv"))

        # Owner can complete normally.
        ok = reg.complete("j1", "alice", success=True)
        self.assertIsNotNone(ok)

    def test_registry_complete_allows_empty_worker_id_for_internal_callers(self) -> None:
        reg = InFlightRegistry()
        reg.claim(
            job_id="j2", worker_id="alice", worker_name="alice-pc",
            source_path=r"\\share\foo.mkv", encode_config={},
        )
        # Empty worker_id is the "internal/unknown caller" affordance —
        # legitimate for crash-recovery and coordinator-internal calls.
        ok = reg.complete("j2", "", success=True)
        self.assertIsNotNone(ok)

    def test_registry_unclaim_rejects_foreign_worker(self) -> None:
        reg = InFlightRegistry()
        reg.claim(
            job_id="j3", worker_id="bob", worker_name="bob-pc",
            source_path=r"\\share\bar.mkv", encode_config={},
        )
        # N3 — foreign worker_id must NOT release someone else's job.
        rejected = reg.unclaim("j3", "mallory")
        self.assertIsNone(rejected)
        self.assertTrue(reg.is_in_flight(r"\\share\bar.mkv"))
        # Owner can release.
        ok = reg.unclaim("j3", "bob")
        self.assertIsNotNone(ok)

    # ------------------------------------------------------------------
    # N10 — recently-completed grace TTL prevents re-claim race
    # ------------------------------------------------------------------
    def test_registry_is_in_flight_honors_recent_completion_grace(self) -> None:
        reg = InFlightRegistry()
        src = r"\\share\just-finished.mkv"
        reg.claim(
            job_id="j4", worker_id="alice", worker_name="alice-pc",
            source_path=src, encode_config={},
        )
        self.assertTrue(reg.is_in_flight(src))
        reg.complete("j4", "alice", success=True)
        # N10 — grace window keeps is_in_flight=True briefly so a
        # second worker doesn't re-claim before the UI thread drops
        # the record from queue_records.
        self.assertTrue(reg.is_in_flight(src))

    def test_registry_grace_expires_after_ttl(self) -> None:
        reg = InFlightRegistry()
        src = r"\\share\old.mkv"
        reg.claim(
            job_id="j5", worker_id="alice", worker_name="alice-pc",
            source_path=src, encode_config={},
        )
        reg.complete("j5", "alice", success=True)
        # Force expiry by rewriting the recent-completion timestamp to
        # well past the TTL.
        reg._recent_completions[src] = 0.0
        self.assertFalse(reg.is_in_flight(src))
        # Pruned on access — entry must be gone afterwards.
        self.assertNotIn(src, reg._recent_completions)

    # ------------------------------------------------------------------
    # N15 — worker rejects oversized coordinator response
    # ------------------------------------------------------------------
    def test_http_read_capped_rejects_oversized_response(self) -> None:
        class FakeResp:
            def __init__(self, payload: bytes) -> None:
                self._payload = payload
            def read(self, n: int = -1) -> bytes:
                return self._payload[:n] if n >= 0 else self._payload

        ok_resp = FakeResp(b'{"status":"ok"}')
        self.assertEqual(_http_read_capped(ok_resp, max_bytes=1024), b'{"status":"ok"}')

        big_resp = FakeResp(b"X" * (10 * 1024))
        with self.assertRaises(RuntimeError):
            _http_read_capped(big_resp, max_bytes=1024)

    # ------------------------------------------------------------------
    # N17 — coordinator URL validation
    # ------------------------------------------------------------------
    def test_validate_coordinator_url_accepts_well_formed(self) -> None:
        self.assertEqual(
            _validate_coordinator_url("http://192.168.1.10:7830"),
            "http://192.168.1.10:7830",
        )
        # Trailing slash stripped.
        self.assertEqual(
            _validate_coordinator_url("http://host:7830/"),
            "http://host:7830",
        )
        self.assertEqual(
            _validate_coordinator_url("https://coord.lan:8443"),
            "https://coord.lan:8443",
        )

    # ------------------------------------------------------------------
    # N4 — body size cap is enforced at the handler level
    # ------------------------------------------------------------------
    def test_coordinator_handler_advertises_body_size_cap(self) -> None:
        from mediapipeline_desktop_app.network.coordinator import _CoordHandler
        # The cap must be set and reasonable (1 MB is the chosen value;
        # accept any value <= 4 MB to allow future tuning).
        self.assertGreater(_CoordHandler.MAX_BODY_BYTES, 0)
        self.assertLessEqual(_CoordHandler.MAX_BODY_BYTES, 4 * 1024 * 1024)

    def test_coordinator_oversized_request_response_failure_is_logged(self) -> None:
        class BadOversizedHandler:
            MAX_BODY_BYTES = _CoordHandler.MAX_BODY_BYTES

            def __init__(self) -> None:
                self.headers = {"Content-Length": str(_CoordHandler.MAX_BODY_BYTES + 1)}
                self.rfile = io.BytesIO(b"")
                self.wfile = io.BytesIO()

            def send_response(self, _status: int) -> None:
                raise RuntimeError("socket closed")

            def send_header(self, _key: str, _value: str) -> None:
                return None

            def end_headers(self) -> None:
                return None

        handler = BadOversizedHandler()

        with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="WARNING") as logs:
            result = _CoordHandler._read_body(handler)  # type: ignore[arg-type]

        self.assertIsNone(result)
        output = "\n".join(logs.output)
        self.assertIn("Failed to send oversized coordinator request response", output)
        self.assertIn("client may not receive 413", output)
        self.assertIn("socket closed", output)

    def test_coordinator_malformed_content_length_response_failure_is_logged(self) -> None:
        class BadMalformedLengthHandler:
            MAX_BODY_BYTES = _CoordHandler.MAX_BODY_BYTES
            _send_json = _CoordHandler._send_json

            def __init__(self) -> None:
                self.headers = {"Content-Length": "not-int"}
                self.rfile = io.BytesIO(b"")
                self.wfile = io.BytesIO()

            def send_response(self, _status: int) -> None:
                raise RuntimeError("socket closed")

            def send_header(self, _key: str, _value: str) -> None:
                return None

            def end_headers(self) -> None:
                return None

        handler = BadMalformedLengthHandler()

        with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="WARNING") as logs:
            result = _CoordHandler._read_body(handler)  # type: ignore[arg-type]

        self.assertIsNone(result)
        output = "\n".join(logs.output)
        self.assertIn("Failed to send malformed Content-Length coordinator request response", output)
        self.assertIn("client may not receive 400", output)
        self.assertIn("socket closed", output)

    def test_coordinator_request_body_read_failure_is_logged(self) -> None:
        class BadBodyStream:
            def read(self, _length: int) -> bytes:
                raise OSError("body stream closed")

        class BadReadHandler:
            MAX_BODY_BYTES = _CoordHandler.MAX_BODY_BYTES

            def __init__(self) -> None:
                self.headers = {"Content-Length": "12"}
                self.rfile = BadBodyStream()
                self.wfile = io.BytesIO()

        handler = BadReadHandler()

        with self.assertLogs("mediapipeline_desktop_app.network.coordinator", level="WARNING") as logs:
            result = _CoordHandler._read_body(handler)  # type: ignore[arg-type]

        self.assertIsNone(result)
        output = "\n".join(logs.output)
        self.assertIn("Failed to read coordinator request body after Content-Length 12", output)
        self.assertIn("request handler will stop", output)
        self.assertIn("body stream closed", output)

    # ------------------------------------------------------------------
    # N13 — worker_id format validation
    # ------------------------------------------------------------------
    def test_worker_id_pattern_admits_uuids_and_machine_ids(self) -> None:
        from mediapipeline_desktop_app.network.coordinator import (
            _WORKER_ID_PATTERN, _WORKER_ID_MAX_LEN,
        )
        # UUID-shaped identifiers must pass.
        self.assertTrue(_WORKER_ID_PATTERN.match("550e8400-e29b-41d4-a716-446655440000"))
        # Hostname-style names with dots and underscores.
        self.assertTrue(_WORKER_ID_PATTERN.match("worker_01.lan"))
        # Plain alphanumeric.
        self.assertTrue(_WORKER_ID_PATTERN.match("BEAST-PC"))
        # Length cap is generous but bounded.
        self.assertGreaterEqual(_WORKER_ID_MAX_LEN, 36)
        self.assertLessEqual(_WORKER_ID_MAX_LEN, 256)

    def test_worker_id_pattern_rejects_problem_characters(self) -> None:
        from mediapipeline_desktop_app.network.coordinator import _WORKER_ID_PATTERN
        # Spaces, control chars, path separators, and query-string
        # tokens must all be rejected.
        self.assertFalse(_WORKER_ID_PATTERN.match("worker 01"))
        self.assertFalse(_WORKER_ID_PATTERN.match("worker\t01"))
        self.assertFalse(_WORKER_ID_PATTERN.match("worker/01"))
        self.assertFalse(_WORKER_ID_PATTERN.match("worker?id=1"))
        self.assertFalse(_WORKER_ID_PATTERN.match("'); drop table workers --"))
        # Empty must not match.
        self.assertFalse(_WORKER_ID_PATTERN.match(""))

    def test_worker_identity_helper_preserves_legacy_validation_rules(self) -> None:
        self.assertTrue(is_valid_worker_id("550e8400-e29b-41d4-a716-446655440000"))
        self.assertTrue(is_valid_worker_id("worker_01.lan"))
        self.assertFalse(is_valid_worker_id("worker 01"))
        self.assertFalse(is_valid_worker_id("worker/01"))
        self.assertFalse(is_valid_worker_id(""))

    def test_worker_name_helper_clips_and_replaces_display_only_names(self) -> None:
        self.assertEqual(coerce_worker_name("", "worker-123456"), "worker-1")
        self.assertEqual(coerce_worker_name("Worker 😀", "worker-123456"), "Worker _")
        self.assertEqual(len(coerce_worker_name("x" * 100, "worker-123456")), 80)

    def test_worker_hostname_lookup_failure_is_logged(self) -> None:
        with (
            patch("mediapipeline_desktop_app.network.worker.socket.gethostname", side_effect=OSError("hostname unavailable")),
            self.assertLogs("mediapipeline_desktop_app.network.worker", level="WARNING") as logs,
        ):
            self.assertEqual(_safe_hostname(), "worker")

        self.assertIn("Worker hostname lookup failed; using fallback worker name", "\n".join(logs.output))

    def test_log_entry_sanitizer_preserves_partial_diagnostics(self) -> None:
        entry = LogEntryRequest(
            worker_id="bad id",
            worker_name="n" * 100,
            job_id="bad/job",
            event="e" * 80,
            message="m" * 4097,
        )

        sanitize_log_entry_fields(entry)

        self.assertEqual(entry.worker_id, "")
        self.assertEqual(entry.job_id, "")
        self.assertEqual(len(entry.worker_name), 80)
        self.assertEqual(len(entry.event), 64)
        self.assertTrue(entry.message.endswith(LOG_MESSAGE_TRUNCATION_SUFFIX))
        self.assertEqual(len(entry.message), 4096 + len(LOG_MESSAGE_TRUNCATION_SUFFIX))

    def test_validate_coordinator_url_rejects_malformed(self) -> None:
        # Missing scheme.
        with self.assertRaises(ValueError):
            _validate_coordinator_url("192.168.1.10:7830")
        # Disallowed scheme.
        with self.assertRaises(ValueError):
            _validate_coordinator_url("ftp://host:21")
        # Has a path segment.
        with self.assertRaises(ValueError):
            _validate_coordinator_url("http://host:7830/api/claim")
        # Has a query string.
        with self.assertRaises(ValueError):
            _validate_coordinator_url("http://host:7830/?evil=1")
        # Embeds userinfo.
        with self.assertRaises(ValueError):
            _validate_coordinator_url("http://user:pass@host:7830")
        # Empty.
        with self.assertRaises(ValueError):
            _validate_coordinator_url("")
        with self.assertRaises(ValueError):
            _validate_coordinator_url("   ")


if __name__ == '__main__':
    unittest.main()
