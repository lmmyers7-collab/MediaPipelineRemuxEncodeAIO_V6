from __future__ import annotations

import io
import json
import socket
import sys
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.network.auth import (
    AUTH_FAILURE_CLOCK_SKEW,
    LEGACY_BEARER_ENV_VAR,
    sign_request,
    validate_header,
    validate_request_auth,
    validate_request_auth_result,
    validate_signed_request,
    validate_signed_request_result,
)
from mediapipeline.core.network.url_policy import redact_network_secret_text, redact_url
from mediapipeline.desktop.config_keys import KEY_COORDINATOR_AUTH_TOKEN
from mediapipeline.desktop.network.coordinator import CoordinatorDispatcher, _CoordHandler, _CoordServer
from mediapipeline.desktop.network.identity import (
    LOG_MESSAGE_TRUNCATION_SUFFIX,
    coerce_worker_name,
    is_valid_worker_id,
    sanitize_log_entry_fields,
)
from mediapipeline.desktop.network.protocol import DoneRequest, LogEntryRequest
from mediapipeline.desktop.network.registry import InFlightRegistry
from mediapipeline.desktop.network.worker import (
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

    def test_hmac_signed_requests_validate_and_reject_replay_or_tampering(self) -> None:
        token = "s" * 32
        timestamp = 1_700_000_000
        nonce_cache: dict[str, float] = {}
        headers = sign_request(
            "POST",
            "/api/done",
            b'{"job_id":"job-1"}',
            token,
            timestamp=timestamp,
            nonce="nonce-1",
        )

        self.assertTrue(
            validate_signed_request(
                headers,
                token,
                method="POST",
                path_with_query="/api/done",
                body=b'{"job_id":"job-1"}',
                nonce_cache=nonce_cache,
                now=timestamp + 1,
            )
        )
        self.assertFalse(
            validate_signed_request(
                headers,
                token,
                method="POST",
                path_with_query="/api/done",
                body=b'{"job_id":"job-1"}',
                nonce_cache=nonce_cache,
                now=timestamp + 1,
            )
        )
        tampered = sign_request("POST", "/api/done", b"{}", token, timestamp=timestamp, nonce="nonce-2")
        self.assertFalse(
            validate_signed_request(
                tampered,
                token,
                method="POST",
                path_with_query="/api/done",
                body=b'{"job_id":"job-1"}',
                now=timestamp + 1,
            )
        )
        stale = sign_request("GET", "/api/workers", b"", token, timestamp=timestamp, nonce="nonce-3")
        self.assertFalse(
            validate_signed_request(
                stale,
                token,
                method="GET",
                path_with_query="/api/workers",
                body=b"",
                now=timestamp + 301,
            )
        )

    def test_inline_worker_result_artifact_is_bound_to_signed_done_body(self) -> None:
        token = "a" * 32
        timestamp = 1_700_000_000
        payload = DoneRequest(
            job_id="job-inline",
            worker_id="worker-inline",
            success=True,
            worker_result_artifact={
                "SchemaVersion": "local_worker_result.v1",
                "WorkerClaimId": "job-inline",
                "Success": True,
                "OutputPath": r"\\server\handoff\Movie.mkv",
            },
        ).to_dict()
        body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
        headers = sign_request(
            "POST",
            "/api/done",
            body,
            token,
            timestamp=timestamp,
            nonce="inline-artifact",
        )
        tampered = dict(payload)
        tampered["worker_result_artifact"] = {
            **payload["worker_result_artifact"],
            "OutputPath": r"C:\Unapproved\Other.mkv",
        }
        tampered_body = json.dumps(tampered, separators=(",", ":")).encode("utf-8")

        self.assertFalse(
            validate_signed_request(
                headers,
                token,
                method="POST",
                path_with_query="/api/done",
                body=tampered_body,
                now=timestamp,
            )
        )

    def test_future_signed_request_nonce_is_retained_for_full_admissible_window(self) -> None:
        token = "s" * 32
        nonce_cache: dict[str, float] = {}
        headers = sign_request(
            "POST",
            "/api/done",
            b'{}',
            token,
            timestamp=1_300,
            nonce="future-window-nonce",
        )

        accepted = validate_signed_request_result(
            headers,
            token,
            method="POST",
            path_with_query="/api/done",
            body=b'{}',
            nonce_cache=nonce_cache,
            now=1_000,
            max_skew_seconds=300,
        )
        replay = validate_signed_request_result(
            headers,
            token,
            method="POST",
            path_with_query="/api/done",
            body=b'{}',
            nonce_cache=nonce_cache,
            now=1_600,
            max_skew_seconds=300,
        )

        self.assertTrue(accepted.ok)
        self.assertEqual(nonce_cache["future-window-nonce"], 1_600)
        self.assertFalse(replay.ok)

    def test_nonce_cache_fails_closed_at_capacity_without_evicting_valid_entries(self) -> None:
        token = "s" * 32
        nonce_cache = {"still-valid": 1_600.0, "expired": 999.0}

        def validate(nonce: str) -> bool:
            headers = sign_request("POST", "/api/done", b'{}', token, timestamp=1_000, nonce=nonce)
            return validate_signed_request_result(
                headers,
                token,
                method="POST",
                path_with_query="/api/done",
                body=b'{}',
                nonce_cache=nonce_cache,
                now=1_000,
                max_skew_seconds=300,
                max_nonce_cache_entries=2,
            ).ok

        self.assertTrue(validate("new-with-room"))
        self.assertEqual(set(nonce_cache), {"still-valid", "new-with-room"})
        self.assertFalse(validate("rejected-at-capacity"))
        self.assertEqual(set(nonce_cache), {"still-valid", "new-with-room"})

    def test_coordinator_http_accepts_identical_future_signed_mutation_only_once(self) -> None:
        token = "s" * 32
        body = b'{"job_id":"job-1"}'
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._auth_token = token
        dispatcher._auth_nonce_cache = {}
        dispatcher._auth_nonce_lock = threading.Lock()
        mutations: list[bytes] = []

        def record_done(handler: _CoordHandler, request_body: bytes) -> None:
            mutations.append(request_body)
            handler._send_json({"status": "ok"})

        dispatcher._http_done = record_done  # type: ignore[method-assign]
        server = _CoordServer(("127.0.0.1", 0), _CoordHandler)
        server.dispatcher = dispatcher
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        headers = sign_request(
            "POST",
            "/api/done",
            body,
            token,
            timestamp=1_300,
            nonce="future-http-nonce",
        )
        request = urllib.request.Request(
            f"http://127.0.0.1:{server.server_port}/api/done",
            data=body,
            headers=headers,
            method="POST",
        )

        try:
            with patch("mediapipeline.desktop.network.auth.time.time", return_value=1_000):
                with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
                    self.assertEqual(response.status, 200)
            with patch("mediapipeline.desktop.network.auth.time.time", return_value=1_301):
                with self.assertRaises(urllib.error.HTTPError) as exc_info:
                    urllib.request.urlopen(request, timeout=5)  # noqa: S310 - localhost test server
            self.assertEqual(exc_info.exception.code, 401)
            self.assertEqual(mutations, [body])
        finally:
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=5)

    def test_signed_late_terminal_and_release_reports_require_reclaimed_worker_owner(self) -> None:
        token = "o" * 32
        with tempfile.TemporaryDirectory() as td:
            state_path = Path(td) / "coordinator_inflight.json"
            registry = InFlightRegistry()
            for job_id, worker_id, source_path in (
                ("job-terminal", "worker-terminal-owner", r"C:\Media\terminal.mkv"),
                ("job-release", "worker-release-owner", r"C:\Media\release.mkv"),
            ):
                self.assertTrue(
                    registry.claim(
                        job_id=job_id,
                        worker_id=worker_id,
                        worker_name=worker_id,
                        source_path=source_path,
                        encode_config={},
                    )
                )
                with registry._lock:
                    registry._jobs[job_id].last_heartbeat = "2026-01-01T00:00:00+00:00"
            self.assertEqual(
                {job.job_id for job in registry.reclaim_stale(0.01)},
                {"job-terminal", "job-release"},
            )
            registry.save(state_path)

            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._auth_token = token
            dispatcher._auth_nonce_cache = {}
            dispatcher._auth_nonce_lock = threading.Lock()
            dispatcher._registry = registry
            dispatcher._inflight_state_path = lambda: state_path  # type: ignore[assignment]
            removed_sources: list[str] = []
            dispatcher._remove_from_queue = removed_sources.append  # type: ignore[assignment]
            events: list[dict[str, object]] = []
            dispatcher.log_cluster_event = lambda **kwargs: events.append(kwargs)  # type: ignore[assignment]

            server = _CoordServer(("127.0.0.1", 0), _CoordHandler)
            server.dispatcher = dispatcher
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()

            def post_done(payload: dict[str, object], nonce: str) -> tuple[int, dict[str, object]]:
                body = json.dumps(payload).encode("utf-8")
                headers = sign_request("POST", "/api/done", body, token, nonce=nonce)
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/api/done",
                    data=body,
                    headers=headers,
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310 - localhost test server
                        return response.status, json.loads(response.read().decode("utf-8"))
                except urllib.error.HTTPError as exc:
                    return exc.code, json.loads(exc.read().decode("utf-8"))

            try:
                terminal_payload = DoneRequest(
                    job_id="job-terminal",
                    worker_id="worker-foreign",
                    success=True,
                    queue_terminal=True,
                ).to_dict()
                first_status, first_body = post_done(terminal_payload, "late-owner-mismatch-1")
                replay_status, replay_body = post_done(terminal_payload, "late-owner-mismatch-2")
                release_mismatch_status, _ = post_done(
                    DoneRequest(
                        job_id="job-release",
                        worker_id="worker-foreign",
                        released=True,
                    ).to_dict(),
                    "late-release-mismatch",
                )
                release_owner_status, release_owner_body = post_done(
                    DoneRequest(
                        job_id="job-release",
                        worker_id="worker-release-owner",
                        released=True,
                    ).to_dict(),
                    "late-release-owner",
                )
            finally:
                server.shutdown()
                server.server_close()
                server_thread.join(timeout=5)

            self.assertEqual((first_status, replay_status, release_mismatch_status), (403, 403, 403))
            self.assertEqual(first_body["status"], "forbidden")
            self.assertEqual(replay_body["status"], "forbidden")
            self.assertEqual(release_owner_status, 200)
            self.assertEqual(release_owner_body["status"], "late_recorded")
            self.assertEqual(removed_sources, [])
            self.assertEqual(registry.reclaimed_source_quarantine_stats()["count"], 2)

            restored = InFlightRegistry()
            self.assertTrue(restored.load(state_path))
            reports = restored.late_terminal_reports_snapshot()
            self.assertEqual(len(reports), 4)
            self.assertEqual(
                [report["authorization_status"] for report in reports],
                [
                    "rejected_owner_mismatch",
                    "rejected_owner_mismatch",
                    "rejected_owner_mismatch",
                    "accepted",
                ],
            )
            self.assertFalse(any(report["removes_queue_record"] for report in reports))
            self.assertEqual(
                [event["event"] for event in events],
                [
                    "late_terminal_owner_mismatch",
                    "late_terminal_owner_mismatch",
                    "late_terminal_owner_mismatch",
                    "late_release_recorded",
                ],
            )

    def test_signed_late_rerun_rejects_path_and_persisted_batch_identity_mismatches(self) -> None:
        token = "r" * 32
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            source = root / "Movies" / "Movie.mkv"
            source.parent.mkdir(parents=True)
            source.write_bytes(b"source")
            batch_path = root / "State" / "Rerun" / "Network" / "batch-1.json"
            batch_path.parent.mkdir(parents=True)
            batch_path.write_text(
                json.dumps(
                    {
                        "schema_version": "desktop_rerun_network_batch.v1",
                        "batch_id": "batch-other",
                        "rows": [{"row_key": "row-1", "source_path": str(source)}],
                    }
                ),
                encoding="utf-8",
            )
            before = batch_path.read_bytes()
            registry = InFlightRegistry()
            self.assertTrue(
                registry.claim(
                    job_id="job-rerun",
                    worker_id="worker-owner",
                    worker_name="Owner Worker",
                    source_path=str(source),
                    encode_config={},
                    job_kind="csv_rerun_row",
                    claim_metadata={
                        "job_kind": "csv_rerun_row",
                        "rerun_batch_id": "batch-1",
                        "rerun_row_key": "row-1",
                    },
                )
            )
            with registry._lock:
                registry._jobs["job-rerun"].last_heartbeat = "2026-01-01T00:00:00+00:00"
            registry.reclaim_stale(0.01)
            registry_path = root / "State" / "coordinator_inflight.json"

            dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
            dispatcher._app = SimpleNamespace(resolved=SimpleNamespace(state_root=root / "State"))
            dispatcher._auth_token = token
            dispatcher._auth_nonce_cache = {}
            dispatcher._auth_nonce_lock = threading.Lock()
            dispatcher._registry = registry
            dispatcher._inflight_state_path = lambda: registry_path  # type: ignore[assignment]
            removed_sources: list[str] = []
            dispatcher._remove_from_queue = removed_sources.append  # type: ignore[assignment]
            dispatcher.log_cluster_event = lambda **_kwargs: None  # type: ignore[assignment]

            server = _CoordServer(("127.0.0.1", 0), _CoordHandler)
            server.dispatcher = dispatcher
            server_thread = threading.Thread(target=server.serve_forever, daemon=True)
            server_thread.start()

            def post(batch_id: str, nonce: str) -> tuple[int, dict[str, object]]:
                body = json.dumps(
                    DoneRequest(
                        job_id="job-rerun",
                        worker_id="worker-owner",
                        success=True,
                        queue_terminal=True,
                        job_kind="csv_rerun_row",
                        rerun_batch_id=batch_id,
                        rerun_row_key="row-1",
                    ).to_dict()
                ).encode("utf-8")
                request = urllib.request.Request(
                    f"http://127.0.0.1:{server.server_port}/api/done",
                    data=body,
                    headers=sign_request("POST", "/api/done", body, token, nonce=nonce),
                    method="POST",
                )
                try:
                    with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
                        return response.status, json.loads(response.read().decode("utf-8"))
                except urllib.error.HTTPError as exc:
                    return exc.code, json.loads(exc.read().decode("utf-8"))

            try:
                path_status, path_body = post("../outside", "late-rerun-path")
                batch_status, batch_body = post("batch-1", "late-rerun-batch")
            finally:
                server.shutdown()
                server.server_close()
                server_thread.join(timeout=5)

            self.assertEqual((path_status, batch_status), (409, 409))
            self.assertEqual(path_body["error"], "network rerun late report identity mismatch")
            self.assertEqual(batch_body["error"], "network rerun late report identity mismatch")
            self.assertEqual(removed_sources, [])
            self.assertEqual(batch_path.read_bytes(), before)

    def test_hmac_clock_skew_is_diagnosed_only_after_signature_matches(self) -> None:
        token = "s" * 32
        timestamp = 1_700_000_000
        stale = sign_request("GET", "/api/workers", b"", token, timestamp=timestamp, nonce="nonce-skew")

        skew = validate_signed_request_result(
            stale,
            token,
            method="GET",
            path_with_query="/api/workers",
            body=b"",
            now=timestamp + 600,
        )
        self.assertFalse(skew.ok)
        self.assertEqual(skew.reason, AUTH_FAILURE_CLOCK_SKEW)

        wrong_token = validate_signed_request_result(
            stale,
            "x" * 32,
            method="GET",
            path_with_query="/api/workers",
            body=b"",
            now=timestamp + 600,
        )
        self.assertFalse(wrong_token.ok)
        self.assertNotEqual(wrong_token.reason, AUTH_FAILURE_CLOCK_SKEW)

    def test_request_auth_result_reports_clock_skew_reason(self) -> None:
        token = "s" * 32
        timestamp = 1_700_000_000
        stale = sign_request("POST", "/api/heartbeat", b"{}", token, timestamp=timestamp, nonce="nonce-skew-2")

        result = validate_request_auth_result(
            stale,
            token,
            method="POST",
            path_with_query="/api/heartbeat",
            body=b"{}",
        )
        self.assertFalse(result.ok)
        self.assertEqual(result.reason, AUTH_FAILURE_CLOCK_SKEW)

    def test_url_secret_redaction_strips_query_fragment_userinfo_and_assignments(self) -> None:
        self.assertEqual(
            redact_url("http://user:pass@host.test:7830/path?token=secret#frag"),
            "http://host.test:7830/path",
        )
        redacted = redact_network_secret_text(
            "failed http://user:pass@host.test:7830/api?token=secret#frag WorkerAuthToken=abc"
        )
        self.assertIn("http://host.test:7830/api", redacted)
        self.assertNotIn("secret", redacted)
        self.assertNotIn("abc", redacted)

    def test_request_auth_allows_legacy_bearer_only_when_env_enabled(self) -> None:
        token = "s" * 32
        headers = {"Authorization": f"Bearer {token}"}
        with patch.dict("os.environ", {}, clear=True):
            self.assertFalse(
                validate_request_auth(headers, token, method="GET", path_with_query="/api/workers", body=b"")
            )
        with patch.dict("os.environ", {LEGACY_BEARER_ENV_VAR: "1"}, clear=True):
            self.assertTrue(
                validate_request_auth(headers, token, method="GET", path_with_query="/api/workers", body=b"")
            )

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

    def test_load_or_generate_token_rejects_short_configured_token_without_leaking_it(self) -> None:
        weak_token = "weak-token"
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._config = lambda: {KEY_COORDINATOR_AUTH_TOKEN: weak_token}  # type: ignore[assignment]
        dispatcher._app = SimpleNamespace(service=SimpleNamespace(load_app_state=lambda: {}))

        with self.assertNoLogs("mediapipeline.desktop.network.coordinator", level="WARNING"):
            with self.assertRaises(ValueError) as exc_info:
                CoordinatorDispatcher._load_or_generate_token(dispatcher)

        self.assertIn("Configured coordinator auth token is too short", str(exc_info.exception))
        self.assertNotIn(weak_token, str(exc_info.exception))

    def test_load_or_generate_token_accepts_strong_configured_token(self) -> None:
        strong_token = "configured-token-0123456789"
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._config = lambda: {KEY_COORDINATOR_AUTH_TOKEN: strong_token}  # type: ignore[assignment]
        dispatcher._app = SimpleNamespace(
            service=SimpleNamespace(load_app_state=lambda: (_ for _ in ()).throw(AssertionError("state should not load")))
        )

        self.assertEqual(CoordinatorDispatcher._load_or_generate_token(dispatcher), strong_token)

    def test_load_or_generate_token_blank_config_falls_back_to_generated_token(self) -> None:
        saved: list[dict] = []
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._config = lambda: {KEY_COORDINATOR_AUTH_TOKEN: "   "}  # type: ignore[assignment]
        dispatcher._app = SimpleNamespace(
            service=SimpleNamespace(
                load_app_state=lambda: {},
                save_app_state=lambda data: saved.append(dict(data)),
            ),
        )

        with patch("mediapipeline.desktop.network.coordinator_auth.generate_token", return_value="generated-token-123456"):
            token = CoordinatorDispatcher._load_or_generate_token(dispatcher)

        self.assertEqual(token, "generated-token-123456")
        self.assertEqual(saved, [{"coordinator_auth_token": "generated-token-123456"}])

    def test_load_or_generate_token_rejects_short_persisted_token_without_leaking_it(self) -> None:
        weak_token = "weak-state"
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._config = lambda: {}  # type: ignore[assignment]
        dispatcher._app = SimpleNamespace(
            service=SimpleNamespace(load_app_state=lambda: {"coordinator_auth_token": weak_token})
        )

        with self.assertRaises(ValueError) as exc_info:
            CoordinatorDispatcher._load_or_generate_token(dispatcher)

        self.assertIn("Persisted coordinator auth token is too short", str(exc_info.exception))
        self.assertNotIn(weak_token, str(exc_info.exception))

    def test_rotated_auth_token_persistence_failure_is_not_logged_as_persisted(self) -> None:
        dispatcher = CoordinatorDispatcher.__new__(CoordinatorDispatcher)
        dispatcher._auth_token = "old-token"
        dispatcher._app = SimpleNamespace(
            service=SimpleNamespace(
                save_app_state=lambda _data: (_ for _ in ()).throw(RuntimeError("disk read-only"))
            ),
        )
        dispatcher.log_cluster_event = lambda **_kwargs: None  # type: ignore[assignment]

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            with self.assertRaisesRegex(RuntimeError, "Could not persist rotated coordinator token"):
                CoordinatorDispatcher.update_auth_token(dispatcher, "x" * 32)

        log_text = "\n".join(logs.output)
        self.assertIn("Could not persist rotated coordinator token", log_text)
        self.assertEqual(dispatcher._auth_token, "old-token")
        self.assertNotIn("updated live, but persistence failed", log_text)
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

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
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

        with patch("mediapipeline.desktop.network.coordinator_auth.generate_token", return_value="generated-token-123456"):
            with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
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
        from mediapipeline.desktop.network.coordinator import _CoordHandler
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

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
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

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
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

        with self.assertLogs("mediapipeline.desktop.network.coordinator", level="WARNING") as logs:
            result = _CoordHandler._read_body(handler)  # type: ignore[arg-type]

        self.assertIsNone(result)
        output = "\n".join(logs.output)
        self.assertIn("Failed to read coordinator request body after Content-Length 12", output)
        self.assertIn("request handler will stop", output)
        self.assertIn("body stream closed", output)

    def test_coordinator_rejects_transfer_encoding_before_body_read(self) -> None:
        server = _CoordServer(("127.0.0.1", 0), _CoordHandler)
        server.dispatcher = SimpleNamespace()
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        client = socket.create_connection(("127.0.0.1", server.server_port), timeout=2)
        client.settimeout(2)

        try:
            client.sendall(
                b"POST /api/done HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Transfer-Encoding: chunked\r\n\r\n"
            )
            response_parts: list[bytes] = []
            while True:
                response_part = client.recv(4096)
                if not response_part:
                    break
                response_parts.append(response_part)
            response = b"".join(response_parts)
            self.assertIn(b"400 Bad Request", response)
            self.assertIn(b"Connection: close", response)
            self.assertIn(b"unsupported Transfer-Encoding", response)
        finally:
            client.close()
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)

    def test_coordinator_stalled_body_hits_connection_timeout_before_auth(self) -> None:
        class FastTimeoutHandler(_CoordHandler):
            REQUEST_IO_TIMEOUT_SECONDS = 0.15

        auth_calls: list[object] = []
        server = _CoordServer(("127.0.0.1", 0), FastTimeoutHandler)
        server.dispatcher = SimpleNamespace(
            _request_auth_result=lambda *_args, **_kwargs: auth_calls.append(object())
        )
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        client = socket.create_connection(("127.0.0.1", server.server_port), timeout=2)
        client.settimeout(2)

        try:
            started = time.monotonic()
            client.sendall(
                b"POST /api/done HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Content-Length: 64\r\n\r\n"
                b"x"
            )
            try:
                response = client.recv(4096)
            except (ConnectionAbortedError, ConnectionResetError):
                response = b""
            self.assertEqual(response, b"")
            self.assertLess(time.monotonic() - started, 1.5)
            self.assertEqual(auth_calls, [])
        finally:
            client.close()
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)

    def test_coordinator_incomplete_headers_hit_connection_timeout(self) -> None:
        class FastTimeoutHandler(_CoordHandler):
            REQUEST_IO_TIMEOUT_SECONDS = 0.15

        server = _CoordServer(("127.0.0.1", 0), FastTimeoutHandler)
        server.dispatcher = SimpleNamespace()
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        client = socket.create_connection(("127.0.0.1", server.server_port), timeout=2)
        client.settimeout(2)

        try:
            started = time.monotonic()
            client.sendall(b"POST /api/done HTTP/1.1\r\nHost: 127.0.0.1\r\n")
            try:
                response = client.recv(4096)
            except (ConnectionAbortedError, ConnectionResetError):
                response = b""
            self.assertEqual(response, b"")
            self.assertLess(time.monotonic() - started, 1.5)
        finally:
            client.close()
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)

    def test_coordinator_caps_concurrent_unauthenticated_handlers(self) -> None:
        class TwoSlotServer(_CoordServer):
            MAX_CONCURRENT_HANDLERS = 2

        class LongTimeoutHandler(_CoordHandler):
            REQUEST_IO_TIMEOUT_SECONDS = 10.0

        server = TwoSlotServer(("127.0.0.1", 0), LongTimeoutHandler)
        server.dispatcher = SimpleNamespace()
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        clients: list[socket.socket] = []

        try:
            request_prefix = (
                b"POST /api/done HTTP/1.1\r\n"
                b"Host: 127.0.0.1\r\n"
                b"Content-Length: 64\r\n\r\n"
                b"x"
            )
            for _ in range(2):
                client = socket.create_connection(("127.0.0.1", server.server_port), timeout=2)
                client.settimeout(2)
                client.sendall(request_prefix)
                clients.append(client)

            deadline = time.monotonic() + 2.0
            while server._active_request_count() < 2 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(server._active_request_count(), 2)

            excess = socket.create_connection(("127.0.0.1", server.server_port), timeout=2)
            excess.settimeout(2)
            clients.append(excess)
            excess.sendall(request_prefix)
            try:
                response = excess.recv(4096)
            except (ConnectionAbortedError, ConnectionResetError):
                response = b""
            self.assertEqual(response, b"")
            self.assertLessEqual(server._active_request_count(), 2)
        finally:
            for client in clients:
                client.close()
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)

    def test_coordinator_shutdown_abandons_stalled_pre_auth_request(self) -> None:
        class LongTimeoutHandler(_CoordHandler):
            REQUEST_IO_TIMEOUT_SECONDS = 30.0

        server = _CoordServer(("127.0.0.1", 0), LongTimeoutHandler)
        server.dispatcher = SimpleNamespace()
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        client = socket.create_connection(("127.0.0.1", server.server_port), timeout=2)
        client.sendall(
            b"POST /api/done HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Length: 64\r\n\r\n"
            b"x"
        )

        try:
            deadline = time.monotonic() + 2.0
            while server._active_request_count() < 1 and time.monotonic() < deadline:
                time.sleep(0.01)
            self.assertEqual(server._active_request_count(), 1)

            started = time.monotonic()
            server.shutdown()
            server.server_close()
            server_thread.join(timeout=2)
            elapsed = time.monotonic() - started

            self.assertLess(elapsed, 1.5)
            self.assertFalse(server_thread.is_alive())
            self.assertEqual(server.daemon_threads, True)
        finally:
            client.close()
            if server_thread.is_alive():
                server.shutdown()
                server.server_close()
                server_thread.join(timeout=2)

    def test_coordinator_shutdown_joins_authenticated_mutation_cleanup(self) -> None:
        mutation_entered = threading.Event()
        allow_completion = threading.Event()
        mutation_completed = threading.Event()

        def request_auth_result(*_args, **_kwargs) -> SimpleNamespace:
            return SimpleNamespace(ok=True, reason="")

        def finish_done(handler: _CoordHandler, _body: bytes) -> None:
            mutation_entered.set()
            self.assertTrue(allow_completion.wait(timeout=2))
            mutation_completed.set()
            handler._send_json({"status": "ok"})

        server = _CoordServer(("127.0.0.1", 0), _CoordHandler)
        server.dispatcher = SimpleNamespace(
            _request_auth_result=request_auth_result,
            _http_done=finish_done,
        )
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        client = socket.create_connection(("127.0.0.1", server.server_port), timeout=2)
        client.sendall(
            b"POST /api/done HTTP/1.1\r\n"
            b"Host: 127.0.0.1\r\n"
            b"Content-Length: 2\r\n\r\n{}"
        )
        self.assertTrue(mutation_entered.wait(timeout=2))

        def close_server() -> None:
            server.shutdown()
            server.server_close()

        close_thread = threading.Thread(target=close_server, daemon=True)
        close_thread.start()
        try:
            time.sleep(0.1)
            self.assertTrue(close_thread.is_alive())
            self.assertFalse(mutation_completed.is_set())
            allow_completion.set()
            close_thread.join(timeout=2)
            server_thread.join(timeout=2)
            self.assertFalse(close_thread.is_alive())
            self.assertTrue(mutation_completed.is_set())
        finally:
            allow_completion.set()
            client.close()
            if close_thread.is_alive():
                close_thread.join(timeout=2)
            if server_thread.is_alive():
                server.shutdown()
                server.server_close()
                server_thread.join(timeout=2)

    # ------------------------------------------------------------------
    # N13 — worker_id format validation
    # ------------------------------------------------------------------
    def test_worker_id_pattern_admits_uuids_and_machine_ids(self) -> None:
        from mediapipeline.desktop.network.coordinator import (
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
        from mediapipeline.desktop.network.coordinator import _WORKER_ID_PATTERN
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
            patch("mediapipeline.desktop.network.worker.socket.gethostname", side_effect=OSError("hostname unavailable")),
            self.assertLogs("mediapipeline.desktop.network.worker", level="WARNING") as logs,
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
        # Missing explicit coordinator port.
        with self.assertRaises(ValueError):
            _validate_coordinator_url("http://host")
        # Bind-all listen addresses are not valid connect targets for a worker.
        with self.assertRaises(ValueError):
            _validate_coordinator_url("http://0.0.0.0:7830")
        with self.assertRaises(ValueError):
            _validate_coordinator_url("http://[::]:7830")
        # Invalid/out-of-range ports.
        with self.assertRaises(ValueError):
            _validate_coordinator_url("http://host:notaport")
        with self.assertRaises(ValueError):
            _validate_coordinator_url("http://host:70000")
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
