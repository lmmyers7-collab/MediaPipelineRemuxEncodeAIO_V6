from __future__ import annotations

import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.core.completed.open_policy import COMPLETED_OPEN_TARGETS
from mediapipeline.core.diagnostics.open_policy import DIAGNOSTICS_OPEN_TARGETS
from mediapipeline.core.publish.pending_policy import PENDING_PUBLISH_OPEN_TARGETS
from mediapipeline.core.queue.policy_parts.rules import QUEUE_OPEN_SCOPES, QUEUE_OPEN_TARGETS
from mediapipeline.desktop.api.contract_payload import (
    LOCAL_API_AUTH_SCHEME,
    LOCAL_API_CONTRACT_NOTES,
    NETWORK_LIFECYCLE_CONTRACTS,
    REPAIR_RECONCILE_CONTRACTS,
    local_api_contract_payload,
)
from mediapipeline.desktop.api.contract import LOCAL_API_ROUTE_CONTRACT
from mediapipeline.desktop.api.routes_read import GET_ROUTE_HANDLERS


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
        self.assertTrue(payload["network_lifecycle_summary"]["mutation_enabled"])
        self.assertTrue(payload["network_lifecycle_summary"]["frontend_allowed"])
        self.assertEqual(payload["network_lifecycle_summary"]["contract_count"], len(NETWORK_LIFECYCLE_CONTRACTS))
        self.assertEqual(payload["notes"], LOCAL_API_CONTRACT_NOTES)

    def test_contract_payload_copies_route_and_note_rows(self) -> None:
        routes = [{"path": "/api/health", "method": "GET", "auth_required": False}]

        payload = local_api_contract_payload(app_version="v5-test", host="localhost", routes=routes)
        payload["routes"][0]["path"] = "/changed"
        payload["network_lifecycle_contracts"][0]["mutation_enabled"] = False
        payload["network_lifecycle_contracts"][0]["dry_run_contract"]["required_result_fields"].append("changed")
        payload["network_lifecycle_contracts"][0]["source_file_policy"]["source_delete"] = "changed"
        payload["repair_reconcile_contracts"][0]["mutation_enabled"] = True
        payload["repair_reconcile_contracts"][0]["dry_run_contract"]["required_result_fields"].append("changed")
        payload["repair_reconcile_contracts"][0]["source_file_policy"]["source_delete"] = "changed"
        payload["notes"].append("changed")

        self.assertEqual(routes[0]["path"], "/api/health")
        self.assertTrue(NETWORK_LIFECYCLE_CONTRACTS[0]["mutation_enabled"])
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

    def test_launch_preflight_contract_advertises_extra_arg_query_fields(self) -> None:
        routes = {route["path"]: route for route in LOCAL_API_ROUTE_CONTRACT}

        query_keys = set(routes["/api/launch/preflight"]["query_keys"])

        self.assertIn("extra_args", query_keys)
        self.assertIn("allow_extra_args", query_keys)
        self.assertIn("single_file", query_keys)
        self.assertEqual(routes["/api/launch/preflight"]["effect"], "none")

    def test_completed_contract_advertises_query_fields(self) -> None:
        routes = {route["path"]: route for route in LOCAL_API_ROUTE_CONTRACT}

        self.assertTrue(GET_ROUTE_HANDLERS["/api/completed"].needs_query)
        self.assertEqual(
            routes["/api/completed"]["query_keys"],
            ["limit", "force_refresh", "proof", "pending_proof_limit"],
        )
        self.assertEqual(routes["/api/completed"]["effect"], "none")

    def test_file_overrides_effective_contract_discloses_read_only_probe_dependency(self) -> None:
        routes = {route["path"]: route for route in LOCAL_API_ROUTE_CONTRACT}

        effective = routes["/api/queue/file-overrides/effective"]

        self.assertTrue(GET_ROUTE_HANDLERS["/api/queue/file-overrides/effective"].needs_query)
        self.assertEqual(effective["effect"], "none")
        self.assertEqual(effective["query_keys"], ["path"])
        self.assertIn("bounded read-only probe stage", effective["read_dependencies"])
        self.assertIn("file_overrides.json", effective["purpose"])
        self.assertIn("without changing queue policy", effective["purpose"])
        self.assertIn("media files", effective["purpose"])

    def test_tdarr_matrix_console_contracts_are_backend_keyed(self) -> None:
        routes = {route["path"]: route for route in LOCAL_API_ROUTE_CONTRACT}

        latest = routes["/api/diagnostics/tdarr-matrix/latest"]
        runs = routes["/api/diagnostics/tdarr-matrix/runs"]
        compare = routes["/api/diagnostics/tdarr-matrix/compare"]
        evidence = routes["/api/diagnostics/tdarr-matrix/evidence/open"]
        rerun = routes["/api/diagnostics/tdarr-matrix/rerun"]

        self.assertEqual(latest["method"], "GET")
        self.assertEqual(latest["effect"], "none")
        self.assertEqual(latest["query_keys"], ["run_id", "finding_limit"])
        self.assertEqual(latest["response_schema"], "desktop_tdarr_matrix_console.v1")
        self.assertEqual(runs["method"], "GET")
        self.assertEqual(runs["effect"], "none")
        self.assertEqual(compare["method"], "GET")
        self.assertEqual(compare["effect"], "none")
        self.assertEqual(compare["query_keys"], ["left_run_id", "right_run_id", "left", "right"])
        self.assertEqual(compare["response_schema"], "desktop_tdarr_matrix_compare.v1")
        self.assertEqual(evidence["request_keys"], ["run_id", "finding_key", "target"])
        self.assertIn("stdout", evidence["allowed_targets"])
        self.assertIn("source_hashes", evidence["allowed_targets"])
        self.assertEqual(rerun["request_keys"], ["source_run_id", "selection", "finding_keys"])
        self.assertEqual(rerun["allowed_selections"], ["selected", "latest_failures"])
        self.assertIn("/api/diagnostics/tdarr-matrix/latest", GET_ROUTE_HANDLERS)
        self.assertIn("/api/diagnostics/tdarr-matrix/runs", GET_ROUTE_HANDLERS)
        self.assertIn("/api/diagnostics/tdarr-matrix/compare", GET_ROUTE_HANDLERS)
        self.assertTrue(GET_ROUTE_HANDLERS["/api/diagnostics/tdarr-matrix/latest"].needs_query)
        self.assertTrue(GET_ROUTE_HANDLERS["/api/diagnostics/tdarr-matrix/compare"].needs_query)

    def test_shell_open_route_contracts_match_backend_allowlists(self) -> None:
        routes = {route["path"]: route for route in LOCAL_API_ROUTE_CONTRACT}

        self.assertEqual(set(routes["/api/queue/open"]["allowed_targets"]), set(QUEUE_OPEN_TARGETS))
        self.assertEqual(set(routes["/api/queue/open"]["allowed_row_scopes"]), set(QUEUE_OPEN_SCOPES))
        self.assertEqual(set(routes["/api/completed/open"]["allowed_targets"]), set(COMPLETED_OPEN_TARGETS))
        self.assertEqual(set(routes["/api/pending-publish/open"]["allowed_targets"]), set(PENDING_PUBLISH_OPEN_TARGETS))
        self.assertEqual(set(routes["/api/diagnostics/open"]["allowed_targets"]), set(DIAGNOSTICS_OPEN_TARGETS))
        self.assertEqual(
            routes["/api/diagnostics/tdarr-matrix-audit"]["allowed_actions"],
            [
                "prepare-proof-pack",
                "report",
                "smoke-pack",
                "proof-pack",
                "strict-report",
                "cleanup-plan",
                "cleanup-archive",
                "cleanup-delete",
            ],
        )
        self.assertEqual(
            routes["/api/diagnostics/tdarr-matrix-audit"]["request_keys"],
            ["action", "confirm_delete_full_matrix"],
        )
        self.assertEqual(routes["/api/maintenance/dependency-atlas/open-folder"]["allowed_targets"], ["dependency_atlas_folder"])

    def test_settings_patch_contract_advertises_library_profile_resets(self) -> None:
        routes = {route["path"]: route for route in LOCAL_API_ROUTE_CONTRACT}

        self.assertIn("library_profile_resets", routes["/api/settings/preview-patch"]["request_keys"])
        self.assertIn("library_profile_resets", routes["/api/settings/save-patch"]["request_keys"])

    def test_library_route_map_read_contracts_are_evidence_only(self) -> None:
        routes = {route["path"]: route for route in LOCAL_API_ROUTE_CONTRACT}
        expected = {
            "/api/libraries/route-map": ("library_route_map.v1", []),
            "/api/libraries/route-map/trace": (
                "library_route_trace.v1",
                ["row_key", "id", "source_path", "path", "output_path"],
            ),
            "/api/libraries/route-map/compare": (
                "library_profile_compare.v1",
                ["left_id", "right_id", "left", "right"],
            ),
            "/api/libraries/route-map/validation": (
                "library_route_validation_handoff.v1",
                ["limit"],
            ),
        }

        for route, (schema, query_keys) in expected.items():
            with self.subTest(route=route):
                contract = routes[route]
                self.assertEqual(contract["method"], "GET")
                self.assertTrue(contract["auth_required"])
                self.assertEqual(contract["effect"], "none")
                self.assertEqual(contract["response_schema"], schema)
                self.assertEqual(contract.get("query_keys", []), query_keys)
                self.assertIn(route, GET_ROUTE_HANDLERS)
                purpose = contract["purpose"].casefold()
                self.assertTrue("without" in purpose or "no " in purpose, contract["purpose"])
                self.assertTrue(
                    any(term in purpose for term in ("saving", "save", "launch", "mutating", "mutation")),
                    contract["purpose"],
                )

        self.assertFalse(GET_ROUTE_HANDLERS["/api/libraries/route-map"].needs_query)
        self.assertTrue(GET_ROUTE_HANDLERS["/api/libraries/route-map/trace"].needs_query)
        self.assertTrue(GET_ROUTE_HANDLERS["/api/libraries/route-map/compare"].needs_query)
        self.assertTrue(GET_ROUTE_HANDLERS["/api/libraries/route-map/validation"].needs_query)

    def test_sample_validation_contract_advertises_category_payload(self) -> None:
        routes = {route["path"]: route for route in LOCAL_API_ROUTE_CONTRACT}
        expected_keys = {
            "schema",
            "shell",
            "source_path",
            "output_path",
            "sample_label",
            "sample_category",
            "proof_strength",
            "operator_decision",
            "checks",
            "evidence",
            "operator_notes",
        }

        for route in ("/api/sample-validation/preview", "/api/sample-validation/append"):
            with self.subTest(route=route):
                request_keys = routes[route]["request_keys"]
                self.assertTrue(expected_keys.issubset(set(request_keys)))

        self.assertEqual(routes["/api/sample-validation/preview"]["effect"], "none")
        self.assertEqual(routes["/api/sample-validation/append"]["effect"], "validation-log-write")

    def test_queue_source_path_contracts_include_library_profile_roots(self) -> None:
        routes = {route["path"]: route for route in LOCAL_API_ROUTE_CONTRACT}

        for route in (
            "/api/queue/priority",
            "/api/queue/file-overrides",
            "/api/queue/file-overrides/route-preview",
            "/api/queue/file-overrides/series-preview",
            "/api/queue/file-overrides/series-apply",
            "/api/queue/file-overrides/folder-preview",
            "/api/queue/file-overrides/folder-rule",
        ):
            with self.subTest(route=route):
                purpose = routes[route]["purpose"]
                self.assertIn("configured source roots", purpose)
                self.assertIn("LibraryProfiles source roots", purpose)

    def test_network_lifecycle_contracts_are_route_available_and_backend_owned(self) -> None:
        payload = local_api_contract_payload(app_version="v5-test", host="127.0.0.1")

        candidate_commands = {contract["candidate_command"] for contract in payload["network_lifecycle_contracts"]}
        self.assertIn("network.coordinator.start", candidate_commands)
        self.assertIn("network.coordinator.stop", candidate_commands)
        self.assertIn("network.worker.polling_lifecycle", candidate_commands)
        for contract in payload["network_lifecycle_contracts"]:
            with self.subTest(contract=contract["key"]):
                self.assertEqual(contract["current_status"], "backend_route_available_provider_guarded")
                self.assertTrue(contract["mutation_enabled"])
                self.assertTrue(contract["frontend_allowed"])
                self.assertTrue(contract["required_preconditions"])
                self.assertTrue(contract["required_evidence"])
                self.assertTrue(contract["rollback_requirements"])
                self.assertTrue(contract["must_not"])

    def test_network_lifecycle_routes_advertise_dry_run_and_confirmed_controls(self) -> None:
        payload = local_api_contract_payload(app_version="v5-test", host="127.0.0.1")
        routes = {route["path"]: route for route in payload["routes"]}
        expected = {
            "/api/network/coordinator/start-dry-run": "none",
            "/api/network/coordinator/stop-dry-run": "none",
            "/api/network/worker/start-dry-run": "none",
            "/api/network/worker/stop-dry-run": "none",
            "/api/network/coordinator/start": "backend-lifecycle",
            "/api/network/coordinator/stop": "backend-lifecycle",
            "/api/network/worker/start": "backend-lifecycle",
            "/api/network/worker/stop": "backend-lifecycle",
        }

        for route, effect in expected.items():
            with self.subTest(route=route):
                self.assertIn(route, routes)
                self.assertEqual(routes[route]["method"], "POST")
                self.assertEqual(routes[route]["effect"], effect)
                self.assertEqual(routes[route]["owner"], "Network")
                self.assertTrue(routes[route]["frontend_exposed"])
                self.assertEqual(routes[route]["requires_confirmation"], effect != "none")
                self.assertEqual(routes[route]["journaled"], effect != "none")
                self.assertEqual(routes[route]["response_schema"], "desktop_command_result.v1")
                if effect == "none":
                    self.assertEqual(routes[route]["data_schema"], "desktop_network_lifecycle_dry_run.v1")
                else:
                    self.assertEqual(routes[route]["data_schema"], "desktop_network_lifecycle_result.v1")
                lifecycle = routes[route]["network_lifecycle"]
                expected_role = "worker" if "/worker/" in route else "coordinator"
                expected_action = "stop" if "/stop" in route else "start"
                self.assertEqual(lifecycle["role"], expected_role)
                self.assertEqual(lifecycle["action"], expected_action)
                self.assertEqual(lifecycle["dry_run"], route.endswith("-dry-run"))

        test_connection = routes["/api/network/worker/test-connection"]
        self.assertEqual(test_connection["method"], "POST")
        self.assertEqual(test_connection["effect"], "none")
        self.assertEqual(test_connection["owner"], "Network")
        self.assertTrue(test_connection["frontend_exposed"])
        self.assertFalse(test_connection["requires_confirmation"])
        self.assertFalse(test_connection["journaled"])
        self.assertEqual(test_connection["request_keys"], ["timeout_seconds"])
        self.assertEqual(test_connection["response_schema"], "desktop_command_result.v1")
        self.assertEqual(test_connection["data_schema"], "desktop_network_worker_test_connection.v1")
        self.assertNotIn("network_lifecycle", test_connection)

        discovery = routes["/api/network/worker/discover-coordinators"]
        self.assertEqual(discovery["method"], "POST")
        self.assertEqual(discovery["effect"], "none")
        self.assertEqual(discovery["owner"], "Network")
        self.assertTrue(discovery["frontend_exposed"])
        self.assertFalse(discovery["requires_confirmation"])
        self.assertFalse(discovery["journaled"])
        self.assertEqual(discovery["request_keys"], ["timeout_seconds"])
        self.assertEqual(discovery["response_schema"], "desktop_command_result.v1")
        self.assertEqual(discovery["data_schema"], "desktop_network_coordinator_discovery.v1")
        self.assertNotIn("network_lifecycle", discovery)

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
                self.assertIn("dry_run_writes", dry_run["required_result_fields"])
                self.assertIn("confirmed_route_would_write", dry_run["required_result_fields"])
                self.assertNotIn("would_write_state", dry_run["required_result_fields"])
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
                    "/api/queue/file-overrides/series-preview": "read-only-preview",
                    "/api/subtitle-qa/preview": "read-only-preview",
                    "/api/ui-preferences": "ui-state-write",
                }.get(str(route["path"]), "none")
                self.assertEqual(route["effect"], expected_effect, route["path"])

        self.assertEqual(
            sorted(non_command_result_posts),
            [
                "/api/queue/file-overrides/folder-preview",
                "/api/queue/file-overrides/route-preview",
                "/api/queue/file-overrides/series-preview",
                "/api/rename/preview",
                "/api/sample-validation/preview",
                "/api/subtitle-qa/preview",
                "/api/ui-preferences",
            ],
        )
        self.assertIn("allow_outside_configured_roots", routes["/api/rename/apply"]["request_keys"])
        self.assertIn("outside-root confirmation", routes["/api/rename/apply"]["purpose"])

    def test_rename_browse_contract_includes_folder_files_mode(self) -> None:
        payload = local_api_contract_payload(app_version="v5-test", host="127.0.0.1")
        routes = {route["path"]: route for route in payload["routes"]}

        self.assertEqual(routes["/api/rename/clean-filename-preview"]["effect"], "none")
        self.assertEqual(routes["/api/rename/clean-filename-preview"]["response_schema"], "desktop_rename_clean_filename_preview.v1")
        self.assertIn("movie_filter_terms", routes["/api/rename/clean-filename-preview"]["query_keys"])
        self.assertNotIn("movie_filter_terms_enabled", routes["/api/rename/clean-filename-preview"]["query_keys"])
        self.assertEqual(routes["/api/rename/movie-cleaning-filters"]["effect"], "none")
        self.assertEqual(routes["/api/rename/movie-cleaning-filters"]["response_schema"], "desktop_rename_movie_filter_catalog.v1")
        self.assertEqual(
            routes["/api/rename/browse"]["allowed_selection_modes"],
            ["files", "folder", "folder_files"],
        )

    def test_full_contract_keeps_effectful_routes_token_protected(self) -> None:
        known_effects = {
            "none",
            "app-state-write",
            "audit-state-write",
            "backend-lifecycle",
            "bounded-health-check",
            "config-write",
            "control-state-write",
            "control-flag-write",
            "diagnostic-process",
            "filesystem-mutation",
            "failure-marker-write",
            "metrics-backfill-state-write",
            "metrics-state-write",
            "process-dry-run",
            "deployment-write",
            "process-launch",
            "queue-state-write",
            "read-only-preview",
            "report-file-write",
            "secret-transfer",
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
