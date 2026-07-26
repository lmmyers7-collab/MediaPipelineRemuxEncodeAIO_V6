from __future__ import annotations

from datetime import UTC, datetime
import json
import tempfile
import threading
import unittest
from pathlib import Path
from typing import Any, Callable
from unittest.mock import patch

from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.api.command_journal import CommandJournal
from mediapipeline.desktop.api import handler_policy
from mediapipeline.desktop.api.handler_policy import OperatorRouteError
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from tests.python.desktop.application_facade_test_support import (
    DummyFacadeService,
    LocalApiHttpTestMixin,
    _resolved,
)


COMMAND_ID = "adversarial-command-001"
COMMAND_HEADER = "X-MediaPipeline-Command-ID"


def _result(command: str, mutation_count: int) -> dict[str, Any]:
    return {
        "schema_version": "desktop_command_result.v1",
        "command": command,
        "ok": True,
        "severity": "info",
        "message": f"Mutation {mutation_count} accepted.",
        "data": {"mutation_count": mutation_count},
    }


def _accepted_payload(route: str, command_id: str) -> dict[str, Any]:
    return {
        "schema_version": "desktop_command_result.v1",
        "command": route.removeprefix("/api/").replace("/", "."),
        "ok": True,
        "severity": "info",
        "message": "Critical command accepted before mutation.",
        "data": {
            "command_id": command_id,
            "route": route,
            "evidence_phase": "accepted",
            "journal_durability": "strict",
        },
    }


class _MutableClock:
    def __init__(self, value: datetime) -> None:
        self.value = value

    def __call__(self) -> datetime:
        return self.value


class CommandReplayAdversarialTests(LocalApiHttpTestMixin, unittest.TestCase):
    def _server(self, root: Path) -> LocalApiServer:
        resolved = _resolved(root)
        return LocalApiServer(
            MediaPipelineApplicationFacade(DummyFacadeService(root), app_version="v6-test"),
            token="test-token",
            resolved_provider=lambda: resolved,
            command_journal_path=root / "RunLogs" / "local_api_command_history.json",
        )

    def _post_command(
        self,
        server: LocalApiServer,
        route: str,
        payload: dict[str, Any],
        command_id: str = COMMAND_ID,
    ) -> tuple[int, dict[str, Any]]:
        return self._post_json(
            f"{server.url}{route}",
            payload,
            token="test-token",
            extra_headers={COMMAND_HEADER: command_id},
        )

    def _strict_fingerprint(self, route: str, request: dict[str, Any]) -> str:
        fingerprint = getattr(handler_policy, "strict_command_fingerprint", None)
        self.assertTrue(callable(fingerprint), "strict_command_fingerprint is not implemented")
        return str(fingerprint(route, request))

    def _reserve(
        self,
        journal: CommandJournal,
        *,
        command_id: str,
        route: str,
        request: dict[str, Any],
    ) -> dict[str, Any]:
        reserve = getattr(journal, "reserve_strict_command", None)
        self.assertTrue(callable(reserve), "CommandJournal.reserve_strict_command is not implemented")
        fingerprint = self._strict_fingerprint(route, request)
        return dict(
            reserve(
                command_id=command_id,
                route=route,
                request_fingerprint=fingerprint,
                accepted_payload=_accepted_payload(route, command_id),
                request=request,
            )
        )

    def _complete(
        self,
        journal: CommandJournal,
        *,
        command_id: str,
        route: str,
        request: dict[str, Any],
        response_payload: dict[str, Any],
        response_status: int = 200,
    ) -> None:
        complete = getattr(journal, "complete_strict_command", None)
        self.assertTrue(callable(complete), "CommandJournal.complete_strict_command is not implemented")
        complete(
            command_id=command_id,
            route=route,
            request_fingerprint=self._strict_fingerprint(route, request),
            response_payload=response_payload,
            response_status=response_status,
        )

    def _run_simultaneous_requests(
        self,
        *,
        payloads: tuple[dict[str, Any], dict[str, Any]],
    ) -> tuple[list[tuple[int, dict[str, Any]]], int]:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            server = self._server(root)
            start_barrier = threading.Barrier(3)
            first_mutation_entered = threading.Event()
            release_first_mutation = threading.Event()
            one_response_ready = threading.Event()
            count_lock = threading.Lock()
            results_lock = threading.Lock()
            mutation_count = 0
            results: list[tuple[int, dict[str, Any]]] = []
            failures: list[BaseException] = []

            def mutate(_request: dict[str, Any]) -> dict[str, Any]:
                nonlocal mutation_count
                with count_lock:
                    mutation_count += 1
                    ordinal = mutation_count
                if ordinal == 1:
                    first_mutation_entered.set()
                    if not release_first_mutation.wait(timeout=5):
                        raise AssertionError("test did not release the first fake mutation")
                return _result("pipeline.start", ordinal)

            server._pipeline_start_payload = mutate  # type: ignore[method-assign]

            def invoke(payload: dict[str, Any]) -> None:
                try:
                    start_barrier.wait(timeout=5)
                    response = self._post_command(server, "/api/pipeline/start", payload)
                    with results_lock:
                        results.append(response)
                        one_response_ready.set()
                except BaseException as exc:  # pragma: no cover - asserted by the coordinating thread
                    with results_lock:
                        failures.append(exc)
                        one_response_ready.set()

            threads = [threading.Thread(target=invoke, args=(payload,)) for payload in payloads]
            try:
                server.start()
                for thread in threads:
                    thread.start()
                start_barrier.wait(timeout=5)
                self.assertTrue(first_mutation_entered.wait(timeout=5), "no fake mutation reached the barrier")
                self.assertTrue(one_response_ready.wait(timeout=5), "the duplicate request did not resolve while the first mutation was blocked")
            finally:
                release_first_mutation.set()
                for thread in threads:
                    thread.join(timeout=5)
                server.stop()

            self.assertFalse(any(thread.is_alive() for thread in threads))
            self.assertEqual(failures, [])
            return results, mutation_count

    def test_simultaneous_same_id_and_payload_mutates_once_and_blocks_inflight_duplicate(self) -> None:
        results, mutation_count = self._run_simultaneous_requests(
            payloads=({"mode": "validate", "sleep_seconds": 1}, {"mode": "validate", "sleep_seconds": 1}),
        )

        self.assertEqual(mutation_count, 1)
        self.assertEqual(sorted(status for status, _payload in results), [200, 409])
        blocked = next(payload for status, payload in results if status == 409)
        self.assertEqual(blocked["code"], "command_in_progress")
        self.assertFalse(blocked["retryable"])
        self.assertTrue(blocked["retry_with_same_command_id"])
        self.assertFalse(blocked["data"]["mutation_performed"])
        self.assertEqual(blocked["data"]["command_id"], COMMAND_ID)

    def test_simultaneous_same_id_with_different_payload_conflicts_without_second_mutation(self) -> None:
        results, mutation_count = self._run_simultaneous_requests(
            payloads=({"mode": "validate", "sleep_seconds": 1}, {"mode": "validate", "sleep_seconds": 2}),
        )

        self.assertEqual(mutation_count, 1)
        self.assertEqual(sorted(status for status, _payload in results), [200, 409])
        conflict = next(payload for status, payload in results if status == 409)
        self.assertEqual(conflict["code"], "command_id_payload_conflict")
        self.assertFalse(conflict["retryable"])
        self.assertFalse(conflict["data"]["mutation_performed"])
        self.assertEqual(conflict["data"]["command_id"], COMMAND_ID)

    def test_retry_after_completed_action_and_lost_response_replays_historical_result(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            server = self._server(root)
            mutation_count = 0

            def mutate(_request: dict[str, Any]) -> dict[str, Any]:
                nonlocal mutation_count
                mutation_count += 1
                return _result("pipeline.start", mutation_count)

            server._pipeline_start_payload = mutate  # type: ignore[method-assign]
            try:
                server.start()
                first_status, _lost_response = self._post_command(
                    server,
                    "/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                )
                replay_status, replay = self._post_command(
                    server,
                    "/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                )
            finally:
                server.stop()

        self.assertEqual(first_status, 200)
        self.assertEqual(replay_status, 200)
        self.assertEqual(mutation_count, 1)
        self.assertEqual(replay["data"]["command_id"], COMMAND_ID)
        self.assertTrue(replay["data"]["idempotent_replay"])
        self.assertFalse(replay["data"]["mutation_performed"])
        self.assertEqual(replay["data"]["evidence_phase"], "replayed")
        self.assertTrue(replay["data"]["current_state_unverified"])
        self.assertEqual(replay["data"]["original_evidence_phase"], "running")

    def test_retry_after_restart_replays_without_invoking_route_again(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            mutation_count = 0

            def mutate(_request: dict[str, Any]) -> dict[str, Any]:
                nonlocal mutation_count
                mutation_count += 1
                return _result("pipeline.start", mutation_count)

            first_server = self._server(root)
            first_server._pipeline_start_payload = mutate  # type: ignore[method-assign]
            try:
                first_server.start()
                first_status, first = self._post_command(
                    first_server,
                    "/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                )
            finally:
                first_server.stop()

            restarted_server = self._server(root)
            restarted_server._pipeline_start_payload = mutate  # type: ignore[method-assign]
            try:
                restarted_server.start()
                replay_status, replay = self._post_command(
                    restarted_server,
                    "/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                )
            finally:
                restarted_server.stop()

        self.assertEqual(first_status, 200)
        self.assertEqual(replay_status, 200)
        self.assertEqual(mutation_count, 1)
        self.assertEqual(first["data"]["command_id"], COMMAND_ID)
        self.assertEqual(replay["data"]["command_id"], COMMAND_ID)
        self.assertTrue(replay["data"]["idempotent_replay"])
        self.assertFalse(replay["data"]["mutation_performed"])

    def test_reservation_write_interruption_rejects_before_mutation_without_consuming_id(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            server = self._server(root)
            mutation_count = 0

            def mutate(_request: dict[str, Any]) -> dict[str, Any]:
                nonlocal mutation_count
                mutation_count += 1
                return _result("pipeline.start", mutation_count)

            server._pipeline_start_payload = mutate  # type: ignore[method-assign]
            try:
                server.start()
                with patch.object(server.command_journal, "_save_locked", side_effect=OSError("reservation write interrupted")):
                    rejected_status, rejected = self._post_command(
                        server,
                        "/api/pipeline/start",
                        {"mode": "validate", "sleep_seconds": 1},
                    )
                retry_status, retry = self._post_command(
                    server,
                    "/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                )
            finally:
                server.stop()

        self.assertEqual(rejected_status, 503)
        self.assertEqual(rejected["code"], "command_journal_unavailable")
        self.assertEqual(rejected["data"]["evidence_phase"], "rejected")
        self.assertEqual(retry_status, 200)
        self.assertEqual(retry["data"]["command_id"], COMMAND_ID)
        self.assertEqual(mutation_count, 1)

    def test_terminal_write_interruption_leaves_indeterminate_reservation_that_blocks_retry(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            server = self._server(root)
            mutation_count = 0
            save_count = 0
            real_save: Callable[..., None] = server.command_journal._save_locked  # type: ignore[method-assign]

            def mutate(_request: dict[str, Any]) -> dict[str, Any]:
                nonlocal mutation_count
                mutation_count += 1
                return _result("pipeline.start", mutation_count)

            def interrupt_terminal(*args: Any, **kwargs: Any) -> None:
                nonlocal save_count
                save_count += 1
                if save_count == 2:
                    raise OSError("terminal write interrupted")
                real_save(*args, **kwargs)

            server._pipeline_start_payload = mutate  # type: ignore[method-assign]
            try:
                server.start()
                with patch.object(server.command_journal, "_save_locked", side_effect=interrupt_terminal):
                    indeterminate_status, indeterminate = self._post_command(
                        server,
                        "/api/pipeline/start",
                        {"mode": "validate", "sleep_seconds": 1},
                    )
                retry_status, retry = self._post_command(
                    server,
                    "/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                )
            finally:
                server.stop()

        self.assertEqual(indeterminate_status, 503)
        self.assertEqual(indeterminate["data"]["evidence_phase"], "indeterminate")
        self.assertTrue(indeterminate["data"]["accepted_reservation_durable"])
        self.assertTrue(indeterminate["data"]["lifecycle_marker_persisted"])
        self.assertEqual(indeterminate["data"]["journal_durability"], "fallback_marker")
        self.assertEqual(mutation_count, 1)
        self.assertIn(retry_status, {409, 503})
        self.assertIn(retry["code"], {"command_in_progress", "command_outcome_indeterminate"})
        self.assertFalse(retry["data"]["mutation_performed"])

    def test_unclassified_dispatch_exception_is_durable_indeterminate_and_replays_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            mutation_count = 0

            def mutate_then_raise(_request: dict[str, Any]) -> dict[str, Any]:
                nonlocal mutation_count
                mutation_count += 1
                raise RuntimeError("synthetic secret after side effect")

            first_server = self._server(root)
            first_server._pipeline_start_payload = mutate_then_raise  # type: ignore[method-assign]
            try:
                first_server.start()
                first_status, first = self._post_command(
                    first_server,
                    "/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                )
                replay_status, replay = self._post_command(
                    first_server,
                    "/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                )
                _history_status, history = self._get_json(
                    f"{first_server.url}/api/commands?limit=10",
                    token="test-token",
                )
            finally:
                first_server.stop()

            restarted = self._server(root)
            restarted._pipeline_start_payload = mutate_then_raise  # type: ignore[method-assign]
            try:
                restarted.start()
                restart_status, restart_replay = self._post_command(
                    restarted,
                    "/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                )
            finally:
                restarted.stop()

        self.assertEqual((first_status, replay_status, restart_status), (503, 503, 503))
        self.assertEqual(mutation_count, 1)
        self.assertEqual(first["code"], "command_outcome_indeterminate")
        self.assertEqual(first["data"]["evidence_phase"], "indeterminate")
        self.assertTrue(first["data"]["current_state_unverified"])
        self.assertNotIn("synthetic secret", json.dumps(first, sort_keys=True))
        self.assertTrue(replay["data"]["idempotent_replay"])
        self.assertEqual(replay["data"]["original_evidence_phase"], "indeterminate")
        self.assertTrue(restart_replay["data"]["idempotent_replay"])
        self.assertEqual(history["entries"][0]["data"]["evidence_phase"], "indeterminate")
        self.assertEqual(history["entries"][0]["data"]["command_id"], COMMAND_ID)
        self.assertFalse(any(entry["command"] == "local_api.route_exception" for entry in history["entries"]))

    def test_explicit_pre_mutation_operator_error_is_durable_failed_terminal(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            server = self._server(root)
            dispatch_count = 0

            def reject_before_mutation(_request: dict[str, Any]) -> dict[str, Any]:
                nonlocal dispatch_count
                dispatch_count += 1
                raise OperatorRouteError(
                    code="synthetic_precondition",
                    operator_message="Synthetic precondition rejected before mutation.",
                    status=503,
                )

            server._pipeline_start_payload = reject_before_mutation  # type: ignore[method-assign]
            try:
                server.start()
                first_status, first = self._post_command(
                    server,
                    "/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                )
                replay_status, replay = self._post_command(
                    server,
                    "/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                )
            finally:
                server.stop()

        self.assertEqual((first_status, replay_status), (503, 503))
        self.assertEqual(dispatch_count, 1)
        self.assertEqual(first["code"], "synthetic_precondition")
        self.assertEqual(first["data"]["evidence_phase"], "failed")
        self.assertFalse(first["data"]["mutation_performed"])
        self.assertTrue(first["data"]["strict_command_journal_recorded"])
        self.assertTrue(replay["data"]["idempotent_replay"])
        self.assertEqual(replay["data"]["original_evidence_phase"], "failed")

    def test_terminal_and_marker_persistence_failure_reports_unresolved_proof_and_blocks_same_identity(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            server = self._server(root)
            mutation_count = 0
            save_count = 0
            real_save: Callable[..., None] = server.command_journal._save_locked  # type: ignore[method-assign]

            def mutate(_request: dict[str, Any]) -> dict[str, Any]:
                nonlocal mutation_count
                mutation_count += 1
                return _result("pipeline.start", mutation_count)

            def interrupt_terminal(*args: Any, **kwargs: Any) -> None:
                nonlocal save_count
                save_count += 1
                if save_count == 2:
                    raise OSError("terminal write interrupted")
                real_save(*args, **kwargs)

            server._pipeline_start_payload = mutate  # type: ignore[method-assign]
            try:
                server.start()
                with (
                    patch.object(server.command_journal, "_save_locked", side_effect=interrupt_terminal),
                    patch("mediapipeline.desktop.api.server.LifecycleLeaseStore.mark_indeterminate", side_effect=OSError("marker denied")),
                ):
                    first_status, first = self._post_command(
                        server,
                        "/api/pipeline/start",
                        {"mode": "validate", "sleep_seconds": 1},
                    )
                retry_status, retry = self._post_command(
                    server,
                    "/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                )
            finally:
                server.stop()

        self.assertEqual(first_status, 503)
        self.assertEqual(first["code"], "command_evidence_unresolved")
        self.assertEqual(first["data"]["evidence_phase"], "unresolved")
        self.assertTrue(first["data"]["accepted_reservation_durable"])
        self.assertFalse(first["data"]["lifecycle_marker_persisted"])
        self.assertNotIn("marker denied", first.get("message", ""))
        self.assertIn(retry_status, {409, 503})
        self.assertFalse(retry["data"]["mutation_performed"])
        self.assertEqual(mutation_count, 1)

    def test_missing_or_raising_state_provider_reports_marker_absence_without_unsafe_retry(self) -> None:
        for provider_mode in ("missing", "raising"):
            with self.subTest(provider_mode=provider_mode), tempfile.TemporaryDirectory() as raw_root:
                root = Path(raw_root)
                server = self._server(root)
                mutation_count = 0
                save_count = 0
                real_save: Callable[..., None] = server.command_journal._save_locked  # type: ignore[method-assign]

                def mutate(_request: dict[str, Any]) -> dict[str, Any]:
                    nonlocal mutation_count
                    mutation_count += 1
                    return _result("pipeline.start", mutation_count)

                def interrupt_terminal(*args: Any, _real_save: Callable[..., None] = real_save, **kwargs: Any) -> None:
                    nonlocal save_count
                    save_count += 1
                    if save_count == 2:
                        raise OSError("terminal write interrupted")
                    _real_save(*args, **kwargs)

                if provider_mode == "missing":
                    server.resolved_provider = lambda: None
                else:
                    def fail_resolved() -> None:
                        raise RuntimeError("resolved provider failed")

                    server.resolved_provider = fail_resolved
                server._pipeline_start_payload = mutate  # type: ignore[method-assign]
                try:
                    server.start()
                    with patch.object(server.command_journal, "_save_locked", side_effect=interrupt_terminal):
                        first_status, first = self._post_command(
                            server,
                            "/api/pipeline/start",
                            {"mode": "validate", "sleep_seconds": 1},
                        )
                    retry_status, retry = self._post_command(
                        server,
                        "/api/pipeline/start",
                        {"mode": "validate", "sleep_seconds": 1},
                    )
                finally:
                    server.stop()

                self.assertEqual(first_status, 503)
                self.assertEqual(first["code"], "command_evidence_unresolved")
                self.assertFalse(first["data"]["lifecycle_marker_persisted"])
                self.assertTrue(first["data"]["accepted_reservation_durable"])
                self.assertIn(retry_status, {409, 503})
                self.assertFalse(retry["data"]["mutation_performed"])
                self.assertEqual(mutation_count, 1)

    def test_incomplete_accepted_record_blocks_same_identity_after_restart(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "RunLogs" / "local_api_command_history.json"
            request = {"mode": "validate", "sleep_seconds": 1}
            first = self._reserve(
                CommandJournal(path=path),
                command_id=COMMAND_ID,
                route="/api/pipeline/start",
                request=request,
            )
            restarted = self._reserve(
                CommandJournal(path=path),
                command_id=COMMAND_ID,
                route="/api/pipeline/start",
                request=request,
            )

        self.assertEqual(first["action"], "execute")
        self.assertEqual(restarted["action"], "blocked")
        self.assertEqual(restarted["code"], "command_in_progress")
        self.assertFalse(restarted["mutation_performed"])

    def test_missing_or_invalid_command_identity_rejects_before_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            server = self._server(root)
            mutation_count = 0

            def mutate(_request: dict[str, Any]) -> dict[str, Any]:
                nonlocal mutation_count
                mutation_count += 1
                return _result("pipeline.start", mutation_count)

            server._pipeline_start_payload = mutate  # type: ignore[method-assign]
            try:
                server.start()
                missing_status, missing = self._post_json(
                    f"{server.url}/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                    token="test-token",
                    extra_headers={COMMAND_HEADER: ""},
                )
                invalid_status, invalid = self._post_json(
                    f"{server.url}/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                    token="test-token",
                    extra_headers={COMMAND_HEADER: "bad id"},
                )
            finally:
                server.stop()

        self.assertEqual((missing_status, invalid_status), (400, 400))
        self.assertEqual(missing["code"], "command_id_required")
        self.assertEqual(invalid["code"], "command_id_invalid")
        self.assertFalse(missing["data"]["mutation_performed"])
        self.assertFalse(invalid["data"]["mutation_performed"])
        self.assertEqual(mutation_count, 0)

    def test_preflight_allows_the_strict_command_identity_header(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            server = self._server(Path(raw_root))
            try:
                server.start()
                status, headers, _body = self._options(
                    f"{server.url}/api/pipeline/start",
                    extra_headers={"Origin": server.url},
                )
            finally:
                server.stop()

        self.assertEqual(status, 204)
        self.assertIn(COMMAND_HEADER, headers.get("Access-Control-Allow-Headers", ""))

    def test_malformed_journal_fails_closed_and_reports_history_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            path = root / "RunLogs" / "local_api_command_history.json"
            path.parent.mkdir(parents=True)
            original_bytes = b"{not valid JSON"
            path.write_bytes(original_bytes)
            server = self._server(root)
            mutation_count = 0

            def mutate(_request: dict[str, Any]) -> dict[str, Any]:
                nonlocal mutation_count
                mutation_count += 1
                return _result("pipeline.start", mutation_count)

            server._pipeline_start_payload = mutate  # type: ignore[method-assign]
            try:
                server.start()
                status, payload = self._post_command(
                    server,
                    "/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                )
                history_status, history = self._get_json(f"{server.url}/api/commands?limit=5", token="test-token")
            finally:
                server.stop()
            preserved_bytes = path.read_bytes()

        self.assertEqual(status, 503)
        self.assertEqual(payload["code"], "command_journal_unavailable")
        self.assertEqual(mutation_count, 0)
        self.assertEqual(history_status, 200)
        self.assertTrue(history["journal_persistence"]["degraded"])
        self.assertEqual(history["journal_persistence"]["json"]["status"], "failed")
        self.assertTrue(history["journal_persistence"]["json"]["last_error"])
        self.assertEqual(preserved_bytes, original_bytes)

    def test_same_id_cannot_cross_command_route_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            server = self._server(root)
            start_count = 0
            control_count = 0

            def start(_request: dict[str, Any]) -> dict[str, Any]:
                nonlocal start_count
                start_count += 1
                return _result("pipeline.start", start_count)

            def control(_request: dict[str, Any]) -> dict[str, Any]:
                nonlocal control_count
                control_count += 1
                return _result("pipeline.control", control_count)

            server._pipeline_start_payload = start  # type: ignore[method-assign]
            server._pipeline_control_payload = control  # type: ignore[method-assign]
            try:
                server.start()
                start_status, _start_payload = self._post_command(
                    server,
                    "/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                )
                control_status, conflict = self._post_command(
                    server,
                    "/api/pipeline/control",
                    {"action": "pause"},
                )
            finally:
                server.stop()

        self.assertEqual(start_status, 200)
        self.assertEqual(control_status, 409)
        self.assertEqual(conflict["code"], "command_id_payload_conflict")
        self.assertEqual(start_count, 1)
        self.assertEqual(control_count, 0)

    def test_strict_confirmation_rejection_records_history_but_does_not_reserve_id(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            server = self._server(root)
            mutation_count = 0

            def stop_audit(_request: dict[str, Any]) -> dict[str, Any]:
                nonlocal mutation_count
                mutation_count += 1
                return _result("audit.stop", mutation_count)

            server._audit_stop_payload = stop_audit  # type: ignore[method-assign]
            try:
                server.start()
                rejected_status, rejected = self._post_command(
                    server,
                    "/api/audit/stop",
                    {"confirm_stop": "true", "reason": "adversarial invalid confirmation"},
                )
                accepted_status, accepted = self._post_command(
                    server,
                    "/api/audit/stop",
                    {"confirm_stop": True, "reason": "operator confirmed"},
                )
                replay_status, replay = self._post_command(
                    server,
                    "/api/audit/stop",
                    {"confirm_stop": True, "reason": "operator confirmed"},
                )
                _history_status, history = self._get_json(f"{server.url}/api/commands?limit=10", token="test-token")
            finally:
                server.stop()

        self.assertEqual(rejected_status, 400)
        self.assertIn("confirm_stop", rejected["error"])
        self.assertEqual(accepted_status, 200)
        self.assertEqual(replay_status, 200)
        self.assertEqual(accepted["data"]["command_id"], COMMAND_ID)
        self.assertTrue(replay["data"]["idempotent_replay"])
        self.assertEqual(mutation_count, 1)
        self.assertTrue(any(entry["command"] == "local_api.validation_failed" for entry in history["entries"]))

    def test_equivalent_payloads_with_different_ids_remain_distinct_operator_intents(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            server = self._server(root)
            mutation_count = 0

            def mutate(_request: dict[str, Any]) -> dict[str, Any]:
                nonlocal mutation_count
                mutation_count += 1
                return _result("pipeline.start", mutation_count)

            server._pipeline_start_payload = mutate  # type: ignore[method-assign]
            try:
                server.start()
                first_status, first = self._post_command(
                    server,
                    "/api/pipeline/start",
                    {"mode": "validate", "sleep_seconds": 1},
                    command_id="independent-command-a",
                )
                second_status, second = self._post_command(
                    server,
                    "/api/pipeline/start",
                    {"sleep_seconds": 1, "mode": "validate"},
                    command_id="independent-command-b",
                )
            finally:
                server.stop()

        self.assertEqual((first_status, second_status), (200, 200))
        self.assertEqual(mutation_count, 2)
        self.assertEqual(first["data"]["command_id"], "independent-command-a")
        self.assertEqual(second["data"]["command_id"], "independent-command-b")
        self.assertFalse(first["data"].get("idempotent_replay", False))
        self.assertFalse(second["data"].get("idempotent_replay", False))

    def test_clock_skew_and_future_timestamps_never_expire_completed_identity(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            path = Path(raw_root) / "RunLogs" / "local_api_command_history.json"
            request = {"mode": "validate", "sleep_seconds": 1}
            clock = _MutableClock(datetime(2099, 1, 1, 12, 0, tzinfo=UTC))
            try:
                journal = CommandJournal(path=path, clock=clock)  # type: ignore[call-arg]
            except TypeError as exc:
                self.fail(f"CommandJournal clock injection is not implemented: {exc}")
            reserved = self._reserve(
                journal,
                command_id=COMMAND_ID,
                route="/api/pipeline/start",
                request=request,
            )
            clock.value = datetime(1900, 1, 1, 12, 0, tzinfo=UTC)
            response = _result("pipeline.start", 1)
            self._complete(
                journal,
                command_id=COMMAND_ID,
                route="/api/pipeline/start",
                request=request,
                response_payload=response,
            )
            replay = self._reserve(
                CommandJournal(path=path, clock=clock),  # type: ignore[call-arg]
                command_id=COMMAND_ID,
                route="/api/pipeline/start",
                request=request,
            )

        self.assertEqual(reserved["action"], "execute")
        self.assertEqual(replay["action"], "replay")
        self.assertEqual(replay["response_status"], 200)
        self.assertEqual(replay["response_payload"], response)
        self.assertFalse(replay["mutation_performed"])


if __name__ == "__main__":
    unittest.main()
