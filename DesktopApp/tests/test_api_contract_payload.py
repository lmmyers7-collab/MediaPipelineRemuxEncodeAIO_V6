from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api.contract_payload import (
    LOCAL_API_AUTH_SCHEME,
    LOCAL_API_CONTRACT_NOTES,
    NETWORK_LIFECYCLE_CONTRACTS,
    REPAIR_RECONCILE_CONTRACTS,
    local_api_contract_payload,
)
from mediapipeline_desktop_app.api.contract import LOCAL_API_ROUTE_CONTRACT


class LocalApiContractPayloadTests(unittest.TestCase):
    def test_contract_payload_groups_public_and_token_routes(self) -> None:
        routes = [
            {"path": "/api/health", "method": "GET", "auth_required": False},
            {"path": "/api/pipeline/start", "method": "POST", "auth_required": True, "effect": "process-launch"},
        ]

        payload = local_api_contract_payload(app_version="v5-test", host="127.0.0.1", routes=routes)

        self.assertEqual(payload["schema_version"], "desktop_local_api_contract.v1")
        self.assertEqual(payload["app_version"], "v5-test")
        self.assertEqual(payload["host"], "127.0.0.1")
        self.assertEqual(payload["auth"]["scheme"], LOCAL_API_AUTH_SCHEME)
        self.assertEqual(payload["auth"]["public_routes"], ["/api/health"])
        self.assertEqual(payload["auth"]["token_routes"], ["/api/pipeline/start"])
        self.assertEqual(payload["routes"], routes)
        self.assertEqual(payload["repair_reconcile_summary"]["schema_version"], "desktop_repair_reconcile_contracts.v1")
        self.assertFalse(payload["repair_reconcile_summary"]["mutation_enabled"])
        self.assertFalse(payload["repair_reconcile_summary"]["frontend_allowed"])
        self.assertEqual(payload["repair_reconcile_summary"]["contract_count"], len(REPAIR_RECONCILE_CONTRACTS))
        self.assertEqual(payload["network_lifecycle_summary"]["schema_version"], "desktop_network_lifecycle_contracts.v1")
        self.assertFalse(payload["network_lifecycle_summary"]["mutation_enabled"])
        self.assertFalse(payload["network_lifecycle_summary"]["frontend_allowed"])
        self.assertEqual(payload["network_lifecycle_summary"]["contract_count"], len(NETWORK_LIFECYCLE_CONTRACTS))
        self.assertEqual(payload["notes"], LOCAL_API_CONTRACT_NOTES)

    def test_contract_payload_copies_route_and_note_rows(self) -> None:
        routes = [{"path": "/api/health", "method": "GET", "auth_required": False}]

        payload = local_api_contract_payload(app_version="v5-test", host="localhost", routes=routes)
        payload["routes"][0]["path"] = "/changed"
        payload["network_lifecycle_contracts"][0]["mutation_enabled"] = True
        payload["network_lifecycle_contracts"][0]["dry_run_contract"]["required_result_fields"].append("changed")
        payload["network_lifecycle_contracts"][0]["source_file_policy"]["source_delete"] = "changed"
        payload["repair_reconcile_contracts"][0]["mutation_enabled"] = True
        payload["repair_reconcile_contracts"][0]["dry_run_contract"]["required_result_fields"].append("changed")
        payload["repair_reconcile_contracts"][0]["source_file_policy"]["source_delete"] = "changed"
        payload["notes"].append("changed")

        self.assertEqual(routes[0]["path"], "/api/health")
        self.assertFalse(NETWORK_LIFECYCLE_CONTRACTS[0]["mutation_enabled"])
        self.assertNotIn("changed", NETWORK_LIFECYCLE_CONTRACTS[0]["dry_run_contract"]["required_result_fields"])
        self.assertEqual(NETWORK_LIFECYCLE_CONTRACTS[0]["source_file_policy"]["source_delete"], "forbidden")
        self.assertFalse(REPAIR_RECONCILE_CONTRACTS[0]["mutation_enabled"])
        self.assertNotIn("changed", REPAIR_RECONCILE_CONTRACTS[0]["dry_run_contract"]["required_result_fields"])
        self.assertEqual(REPAIR_RECONCILE_CONTRACTS[0]["source_file_policy"]["source_delete"], "forbidden")
        self.assertNotIn("changed", LOCAL_API_CONTRACT_NOTES)

    def test_contract_payload_defaults_to_full_local_api_contract(self) -> None:
        payload = local_api_contract_payload(app_version="v5-test", host="127.0.0.1")

        self.assertIn("/api/health", payload["auth"]["public_routes"])
        self.assertIn("/api/pipeline/start", payload["auth"]["token_routes"])
        self.assertGreater(len(payload["routes"]), 10)
        self.assertGreaterEqual(len(payload["network_lifecycle_contracts"]), 3)
        self.assertGreaterEqual(len(payload["repair_reconcile_contracts"]), 4)

    def test_network_lifecycle_contracts_are_design_only_and_backend_owned(self) -> None:
        payload = local_api_contract_payload(app_version="v5-test", host="127.0.0.1")

        candidate_commands = {contract["candidate_command"] for contract in payload["network_lifecycle_contracts"]}
        self.assertIn("network.coordinator.start", candidate_commands)
        self.assertIn("network.coordinator.stop", candidate_commands)
        self.assertIn("network.worker.polling_lifecycle", candidate_commands)
        for contract in payload["network_lifecycle_contracts"]:
            with self.subTest(contract=contract["key"]):
                self.assertEqual(contract["current_status"], "design_only_no_route")
                self.assertFalse(contract["mutation_enabled"])
                self.assertFalse(contract["frontend_allowed"])
                self.assertTrue(contract["required_preconditions"])
                self.assertTrue(contract["required_evidence"])
                self.assertTrue(contract["rollback_requirements"])
                self.assertTrue(contract["must_not"])

    def test_network_lifecycle_contracts_define_dry_run_rollback_and_exposure_gates(self) -> None:
        payload = local_api_contract_payload(app_version="v5-test", host="127.0.0.1")

        for contract in payload["network_lifecycle_contracts"]:
            with self.subTest(contract=contract["key"]):
                dry_run = contract["dry_run_contract"]
                rollback = contract["rollback_contract"]
                source_policy = contract["source_file_policy"]
                exposure_gates = contract["route_exposure_gates"]

                self.assertEqual(dry_run["effect"], "none")
                self.assertEqual(dry_run["result_schema"], "desktop_network_lifecycle_dry_run.v1")
                self.assertIn("dry_run_only", dry_run["required_result_fields"])
                self.assertIn("precondition_results", dry_run["required_result_fields"])
                self.assertIn("would_not_touch", dry_run["required_result_fields"])
                self.assertTrue(any("source media" in line for line in dry_run["must_report"]))

                self.assertTrue(rollback["required_for_mutation_route"])
                self.assertTrue(rollback["journal_required"])
                self.assertTrue(rollback["rollback_on"])
                self.assertIn("rollback_status", rollback["journal_fields"])

                self.assertEqual(source_policy["source_media_mutation"], "forbidden")
                self.assertEqual(source_policy["source_delete"], "forbidden")
                self.assertEqual(source_policy["source_path_authority"], "backend_resolved_from_config_and_state_only")

                self.assertTrue(any("API_ROUTE_INVENTORY.md" in gate for gate in exposure_gates))
                self.assertTrue(any("LOCAL_API_ROUTE_CONTRACT" in gate for gate in exposure_gates))
                self.assertTrue(any("DOC_TOUCH_LOG" in gate for gate in exposure_gates))

    def test_repair_reconcile_contracts_are_design_only_and_backend_owned(self) -> None:
        payload = local_api_contract_payload(app_version="v5-test", host="127.0.0.1")

        candidate_commands = {contract["candidate_command"] for contract in payload["repair_reconcile_contracts"]}
        self.assertIn("completed.reconcile_manifest", candidate_commands)
        self.assertIn("completed.repair_sidecar_metadata", candidate_commands)
        self.assertIn("pending_publish.repair_manifest", candidate_commands)
        self.assertIn("pending_publish.reconcile_orphan_payloads", candidate_commands)
        for contract in payload["repair_reconcile_contracts"]:
            with self.subTest(contract=contract["key"]):
                self.assertEqual(contract["current_status"], "design_only_no_route")
                self.assertFalse(contract["mutation_enabled"])
                self.assertFalse(contract["frontend_allowed"])
                self.assertTrue(contract["required_preconditions"])
                self.assertTrue(contract["required_evidence"])
                self.assertTrue(contract["rollback_requirements"])
                self.assertTrue(contract["must_not"])

    def test_repair_reconcile_contracts_define_dry_run_rollback_and_exposure_gates(self) -> None:
        payload = local_api_contract_payload(app_version="v5-test", host="127.0.0.1")

        for contract in payload["repair_reconcile_contracts"]:
            with self.subTest(contract=contract["key"]):
                dry_run = contract["dry_run_contract"]
                rollback = contract["rollback_contract"]
                source_policy = contract["source_file_policy"]
                exposure_gates = contract["route_exposure_gates"]

                self.assertEqual(dry_run["effect"], "none")
                self.assertEqual(dry_run["result_schema"], "desktop_repair_reconcile_dry_run.v1")
                self.assertIn("dry_run_only", dry_run["required_result_fields"])
                self.assertIn("precondition_results", dry_run["required_result_fields"])
                self.assertIn("would_not_touch", dry_run["required_result_fields"])
                self.assertTrue(any("source media" in line for line in dry_run["must_report"]))

                self.assertTrue(rollback["required_for_mutation_route"])
                self.assertTrue(rollback["journal_required"])
                self.assertTrue(rollback["rollback_on"])
                self.assertIn("rollback_status", rollback["journal_fields"])

                self.assertEqual(source_policy["source_media_mutation"], "forbidden")
                self.assertEqual(source_policy["source_delete"], "forbidden")
                self.assertEqual(source_policy["source_path_authority"], "backend_resolved_from_state_only")

                self.assertTrue(any("API_ROUTE_INVENTORY.md" in gate for gate in exposure_gates))
                self.assertTrue(any("LOCAL_API_ROUTE_CONTRACT" in gate for gate in exposure_gates))
                self.assertTrue(any("DOC_TOUCH_LOG" in gate for gate in exposure_gates))

    def test_csv_rerun_route_contract_preserves_copy_keep_park_defaults(self) -> None:
        payload = local_api_contract_payload(app_version="v5-test", host="127.0.0.1")
        routes = {route["path"]: route for route in payload["routes"]}
        rerun_route = routes["/api/rerun/start"]

        self.assertEqual(rerun_route["method"], "POST")
        self.assertEqual(rerun_route["effect"], "process-launch")
        self.assertEqual(
            rerun_route["safe_defaults"],
            {"dry_run": False, "stage_mode": "copy", "original_mode": "keep", "return_mode": "park"},
        )
        self.assertIn("conservative media-safe defaults", rerun_route["purpose"])

    def test_effectful_post_routes_return_command_results_for_operator_history(self) -> None:
        payload = local_api_contract_payload(app_version="v5-test", host="127.0.0.1")
        non_command_result_posts: list[str] = []
        routes = {route["path"]: route for route in payload["routes"]}

        for route in payload["routes"]:
            if route["method"] != "POST":
                continue
            if route["response_schema"] != "desktop_command_result.v1":
                non_command_result_posts.append(str(route["path"]))
                expected_effect = {
                    "/api/queue/file-overrides/folder-preview": "read-only-preview",
                    "/api/queue/file-overrides/route-preview": "read-only-preview",
                    "/api/ui-preferences": "ui-state-write",
                }.get(str(route["path"]), "none")
                self.assertEqual(route["effect"], expected_effect, route["path"])

        self.assertEqual(
            sorted(non_command_result_posts),
            [
                "/api/queue/file-overrides/folder-preview",
                "/api/queue/file-overrides/route-preview",
                "/api/rename/preview",
                "/api/sample-validation/preview",
                "/api/ui-preferences",
            ],
        )
        self.assertIn("allow_outside_configured_roots", routes["/api/rename/apply"]["request_keys"])
        self.assertIn("outside-root confirmation", routes["/api/rename/apply"]["purpose"])

    def test_full_contract_keeps_effectful_routes_token_protected(self) -> None:
        known_effects = {
            "none",
            "app-state-write",
            "backend-lifecycle",
            "bounded-health-check",
            "config-write",
            "control-state-write",
            "control-flag-write",
            "filesystem-mutation",
            "failure-marker-write",
            "process-dry-run",
            "deployment-write",
            "process-launch",
            "queue-state-write",
            "read-only-preview",
            "shell-dialog",
            "shell-open",
            "tooling-artifact-write",
            "ui-state-write",
            "validation-log-write",
        }

        payload = local_api_contract_payload(app_version="v5-test", host="127.0.0.1")

        self.assertEqual(payload["auth"]["public_routes"], ["/api/health"])
        self.assertEqual(len(payload["routes"]), len(LOCAL_API_ROUTE_CONTRACT))
        for route in payload["routes"]:
            with self.subTest(route=route["path"]):
                self.assertIn(route["effect"], known_effects)
                if route["method"] == "POST" or route["effect"] != "none":
                    self.assertTrue(route["auth_required"])


if __name__ == "__main__":
    unittest.main()
