from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from mediapipeline.core.api.commands import COMMAND_ROUTE_METHODS
from mediapipeline.core.processes.lifecycle_lease import LifecycleLeaseStore
from mediapipeline.core.validation.boundary import ValidationFailure, validate_api_payload
from mediapipeline.desktop.api import LocalApiServer
from mediapipeline.desktop.api.contract import LOCAL_API_ROUTE_CONTRACT
from mediapipeline.desktop.api.handler_policy import requires_strict_durable_command_journal
from mediapipeline.desktop.api.routes_command import POST_ROUTE_HANDLERS
from mediapipeline.desktop.application import MediaPipelineApplicationFacade
from tests.python.desktop.application_facade_test_support import (
    DummyWorkflowFacadeService,
    LocalApiHttpTestMixin,
    _resolved,
)


DRY_RUN_ROUTE = "/api/backend/lifecycle/reconcile-dry-run"
APPLY_ROUTE = "/api/backend/lifecycle/reconcile"
RECONCILIATION_SCHEMA = "desktop_lifecycle_reconciliation.v1"


def _rewrite_json(path: Path, **updates: object) -> None:
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload.update(updates)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _build_failed_audit_recovery_chain(state_root: Path) -> None:
    store = LifecycleLeaseStore(state_root, pid_alive=lambda _pid: False)
    recovery_request = {
        "library_root": r"\\server\share\Video",
        "include_sidecars": True,
        "show_console": False,
    }
    interrupted = store.acquire(scope="Audit start", command_id="audit-command-1")
    interrupted.set_recovery_descriptor(route="/api/audit/start", request=recovery_request)
    descriptor = store.begin_one_recovery_attempt()
    recovery_attempt = store.acquire(
        scope="Audit start",
        command_id=str(descriptor["recovery_command_id"]),
        resource_claims=[r"\\server\share\Video"],
    )
    recovery_attempt.set_recovery_descriptor(route="/api/audit/start", request=recovery_request)
    terminal_path = store.root / f"{recovery_attempt.lease_id}.terminal.json"
    recovery_attempt.release(outcome="launch_failed")
    store.mark_indeterminate(
        command_id="audit-command-1",
        route="/api/audit/start",
        reason="Automatic recovery did not produce a successful terminal result.",
    )
    # The public facade uses the production PID reader. Preserve the realistic
    # evidence shape while ensuring this temporary fixture cannot name a live
    # process from the test runner.
    dead_pid = 2_147_483_000
    _rewrite_json(store.recovery_path, owner_pid=dead_pid, child_pid=0)
    _rewrite_json(terminal_path, owner_pid=dead_pid, child_pid=0)


class LifecycleReconciliationApiContractTests(unittest.TestCase):
    def test_command_registry_and_route_contracts_are_exact_mirrors(self) -> None:
        routes = {str(route["path"]): route for route in LOCAL_API_ROUTE_CONTRACT}

        self.assertEqual(
            COMMAND_ROUTE_METHODS[DRY_RUN_ROUTE],
            "_backend_lifecycle_reconcile_dry_run_payload",
        )
        self.assertEqual(
            COMMAND_ROUTE_METHODS[APPLY_ROUTE],
            "_backend_lifecycle_reconcile_payload",
        )
        self.assertEqual(
            POST_ROUTE_HANDLERS[DRY_RUN_ROUTE].method_name,
            COMMAND_ROUTE_METHODS[DRY_RUN_ROUTE],
        )
        self.assertEqual(
            POST_ROUTE_HANDLERS[APPLY_ROUTE].method_name,
            COMMAND_ROUTE_METHODS[APPLY_ROUTE],
        )

        dry_run = routes[DRY_RUN_ROUTE]
        apply = routes[APPLY_ROUTE]
        self.assertEqual(dry_run["method"], "POST")
        self.assertTrue(dry_run["auth_required"])
        self.assertEqual(dry_run["effect"], "none")
        self.assertEqual(dry_run["request_keys"], ["reason"])
        self.assertEqual(dry_run["response_schema"], "desktop_command_result.v1")
        self.assertEqual(dry_run["data_schema"], RECONCILIATION_SCHEMA)
        self.assertFalse(dry_run["requires_confirmation"])
        self.assertFalse(dry_run["journaled"])

        self.assertEqual(apply["method"], "POST")
        self.assertTrue(apply["auth_required"])
        self.assertEqual(apply["effect"], "lifecycle-evidence-reconciliation")
        self.assertEqual(
            apply["request_keys"],
            ["confirm_apply", "dry_run_fingerprint", "reason"],
        )
        self.assertEqual(apply["response_schema"], "desktop_command_result.v1")
        self.assertEqual(apply["data_schema"], RECONCILIATION_SCHEMA)
        self.assertEqual(apply["safe_defaults"], {"confirm_apply": False})
        self.assertEqual(apply["requires_strict_boolean"], ["confirm_apply"])
        self.assertTrue(apply["requires_dry_run_fingerprint"])
        self.assertTrue(apply["requires_confirmation"])
        self.assertTrue(apply["journaled"])
        self.assertTrue(requires_strict_durable_command_journal(APPLY_ROUTE))
        self.assertFalse(requires_strict_durable_command_journal(DRY_RUN_ROUTE))

    def test_request_contracts_reject_caller_selected_paths_pids_and_record_ids(self) -> None:
        self.assertEqual(
            validate_api_payload(DRY_RUN_ROUTE, {"reason": "Operator-reviewed stale audit recovery"}),
            {"reason": "Operator-reviewed stale audit recovery"},
        )
        apply_payload = {
            "confirm_apply": True,
            "dry_run_fingerprint": "preview-fingerprint",
            "reason": "Operator-reviewed stale audit recovery",
        }
        self.assertEqual(validate_api_payload(APPLY_ROUTE, apply_payload), apply_payload)

        caller_selected_evidence = {
            "path": r"C:\LocalBase\State\Lifecycle\recovery-pending.json",
            "archive_path": r"C:\LocalBase\State\Lifecycle\Archive",
            "pid": 1234,
            "owner_pid": 1234,
            "child_pid": 5678,
            "lease_id": "lease-1",
            "command_id": "command-1",
            "record_id": "record-1",
        }
        for route, baseline in (
            (DRY_RUN_ROUTE, {"reason": "review"}),
            (APPLY_ROUTE, apply_payload),
        ):
            for key, value in caller_selected_evidence.items():
                with self.subTest(route=route, rejected_key=key), self.assertRaises(ValidationFailure):
                    validate_api_payload(route, {**baseline, key: value})

    def test_apply_requires_literal_true_and_nonempty_dry_run_fingerprint(self) -> None:
        for confirmation in (None, False, "true", 1):
            payload = {
                "dry_run_fingerprint": "preview-fingerprint",
                "reason": "Operator-reviewed stale audit recovery",
            }
            if confirmation is not None:
                payload["confirm_apply"] = confirmation
            with self.subTest(confirm_apply=confirmation), self.assertRaises(ValidationFailure):
                validate_api_payload(APPLY_ROUTE, payload)

        for fingerprint in (None, "", "   "):
            payload = {
                "confirm_apply": True,
                "reason": "Operator-reviewed stale audit recovery",
            }
            if fingerprint is not None:
                payload["dry_run_fingerprint"] = fingerprint
            with self.subTest(dry_run_fingerprint=fingerprint), self.assertRaises(ValidationFailure):
                validate_api_payload(APPLY_ROUTE, payload)


class LifecycleReconciliationFacadeTests(unittest.TestCase):
    def test_facade_returns_command_results_and_updates_recovery_status_after_apply(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            state_root = root / "State"
            _build_failed_audit_recovery_chain(state_root)
            resolved = _resolved(root)
            resolved.state_root = state_root
            facade = MediaPipelineApplicationFacade(
                DummyWorkflowFacadeService(root),
                app_version="v6-test",
            )
            facade.set_recovery_status(
                {
                    "schema_version": "desktop_lifecycle_recovery.v1",
                    "status": "blocked",
                    "classification": "parked",
                    "operator_action_required": "Automatic resume failed; backend reconciliation is required.",
                    "items": [],
                }
            )

            preview = facade.preview_lifecycle_reconciliation(
                resolved,
                {"reason": "Operator-reviewed stale audit recovery"},
            ).to_mapping()

            self.assertEqual(preview["schema_version"], "desktop_command_result.v1")
            self.assertEqual(preview["command"], "backend.lifecycle.reconcile_dry_run")
            self.assertTrue(preview["ok"])
            self.assertEqual(preview["data"]["schema_version"], RECONCILIATION_SCHEMA)
            self.assertTrue(preview["data"]["safe_to_apply"])
            self.assertTrue(preview["data"]["dry_run_fingerprint"])
            self.assertEqual(preview["data"]["effect"], "none")
            self.assertTrue(preview["data"]["suppress_command_journal"])

            applied = facade.apply_lifecycle_reconciliation(
                resolved,
                {
                    "confirm_apply": True,
                    "dry_run_fingerprint": preview["data"]["dry_run_fingerprint"],
                    "reason": "Operator-reviewed stale audit recovery",
                },
            ).to_mapping()

            self.assertEqual(applied["schema_version"], "desktop_command_result.v1")
            self.assertEqual(applied["command"], "backend.lifecycle.reconcile")
            self.assertTrue(applied["ok"])
            self.assertEqual(applied["data"]["schema_version"], RECONCILIATION_SCHEMA)
            self.assertTrue(applied["data"]["applied"])
            recovery = facade.get_recovery_status()
            self.assertEqual(recovery["schema_version"], "desktop_lifecycle_recovery.v1")
            self.assertEqual(recovery["status"], "complete")
            self.assertEqual(recovery["classification"], "reconciled")
            self.assertEqual(recovery["operator_action_required"], "")


class LifecycleReconciliationLocalApiTests(LocalApiHttpTestMixin, unittest.TestCase):
    def test_post_routes_keep_dry_run_unjournaled_and_apply_strict_durable(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            state_root = root / "State"
            _build_failed_audit_recovery_chain(state_root)
            resolved = _resolved(root)
            resolved.state_root = state_root
            facade = MediaPipelineApplicationFacade(
                DummyWorkflowFacadeService(root),
                app_version="v6-test",
            )
            facade.set_recovery_status(
                {
                    "schema_version": "desktop_lifecycle_recovery.v1",
                    "status": "blocked",
                    "classification": "parked",
                    "operator_action_required": "Reconciliation required.",
                    "items": [],
                }
            )
            server = LocalApiServer(
                facade,
                token="test-token",
                resolved_provider=lambda: resolved,
            )
            try:
                server.start()
                before_status, before = self._get_json(
                    f"{server.url}/api/commands?limit=20",
                    token="test-token",
                )
                dry_status, dry_run = self._post_json(
                    f"{server.url}{DRY_RUN_ROUTE}",
                    {"reason": "Operator-reviewed stale audit recovery"},
                    token="test-token",
                )
                after_dry_status, after_dry = self._get_json(
                    f"{server.url}/api/commands?limit=20",
                    token="test-token",
                )
                apply_status, applied = self._post_json(
                    f"{server.url}{APPLY_ROUTE}",
                    {
                        "confirm_apply": True,
                        "dry_run_fingerprint": dry_run.get("data", {}).get("dry_run_fingerprint", ""),
                        "reason": "Operator-reviewed stale audit recovery",
                    },
                    token="test-token",
                )
                recovery_status, recovery = self._get_json(
                    f"{server.url}/api/backend/recovery-status",
                    token="test-token",
                )
                history_status, history = self._get_json(
                    f"{server.url}/api/commands?limit=20",
                    token="test-token",
                )
            finally:
                server.stop()

        self.assertEqual(before_status, 200)
        self.assertEqual(dry_status, 200)
        self.assertEqual(dry_run["command"], "backend.lifecycle.reconcile_dry_run")
        self.assertEqual(dry_run["data"]["effect"], "none")
        self.assertTrue(dry_run["data"]["suppress_command_journal"])
        self.assertEqual(after_dry_status, 200)
        self.assertEqual(after_dry["count"], before["count"])

        self.assertEqual(apply_status, 200)
        self.assertEqual(applied["command"], "backend.lifecycle.reconcile")
        self.assertTrue(applied["ok"])
        self.assertEqual(applied["data"]["journal_durability"], "strict")
        self.assertTrue(applied["data"]["strict_command_journal_recorded"])
        self.assertTrue(applied["data"]["command_id"])
        self.assertEqual(history_status, 200)
        self.assertGreater(history["count"], after_dry["count"])

        self.assertEqual(recovery_status, 200)
        self.assertEqual(recovery["status"], "complete")
        self.assertEqual(recovery["classification"], "reconciled")


if __name__ == "__main__":
    unittest.main()
