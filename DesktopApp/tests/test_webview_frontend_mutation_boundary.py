from __future__ import annotations

import re
import sys
import unittest
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api.contract import LOCAL_API_ROUTE_CONTRACT
from mediapipeline_desktop_app.api.contract_payload import local_api_contract_payload


REPO_ROOT = Path(__file__).resolve().parents[2]
ASSET_ROOT = REPO_ROOT / "DesktopApp" / "mediapipeline_desktop_app" / "ui_web" / "static" / "assets"
API_POST_LITERAL_RE = re.compile(r"\bapiPost\s*\(\s*(?P<quote>[\"'])(?P<route>/api/[^\"']+)(?P=quote)")
API_POST_CALL_RE = re.compile(r"\bapiPost\s*\(")

EXPECTED_API_POST_OWNERS: dict[str, set[str]] = {
    "/api/backend/shutdown": {"app.js"},
    "/api/ui-preferences": {"app.js"},
    "/api/pipeline/control": {"launchView.js"},
    "/api/pipeline/start": {"launchView.js"},
    "/api/audit/start": {"launchView.js"},
    "/api/rerun/start": {"launchView.js"},
    "/api/completed/open": {"completedView.js"},
    "/api/final-library-promotion/promote-queue": {"completedView.js"},
    "/api/final-library-promotion/pause": {"completedView.js"},
    "/api/final-library-promotion/resume": {"completedView.js"},
    "/api/maintenance/release-dry-run": {"maintenanceView.js"},
    "/api/maintenance/release-build": {"maintenanceView.js"},
    "/api/maintenance/completed-backfill-dry-run": {"maintenanceView.js"},
    "/api/maintenance/dependency-atlas": {"maintenanceView.js"},
    "/api/sample-validation/preview": {"crossPageContextView.sampleValidation.js"},
    "/api/sample-validation/append": {"crossPageContextView.sampleValidation.js"},
    "/api/diagnostics/open": {"diagnosticsView.js"},
    "/api/pending-publish/open": {"pendingPublishView.diagnostics.js"},
    "/api/pending-publish/recovery-plan": {"pendingPublishView.recovery.js"},
    "/api/queue/open": {"queueView.js"},
    "/api/queue/priority": {"queueView.js"},
    "/api/queue/strategy": {"queueView.js"},
    "/api/queue/file-overrides": {"queueView.js"},
    "/api/queue/file-overrides/route-preview": {"queueView.js"},
    "/api/queue/file-overrides/folder-preview": {"queueView.js"},
    "/api/queue/file-overrides/folder-rule": {"queueView.js"},
    "/api/failures/clear": {"reportsView.js"},
    "/api/rename/apply": {"renameView.js"},
    "/api/rename/browse": {"renameView.js"},
    "/api/rename/preview": {"renameView.js"},
    "/api/schedule/preview": {"scheduleView.js"},
    "/api/schedule/save": {"scheduleView.js"},
    "/api/settings/validate": {"settingsView.js"},
    "/api/settings/browse-path": {"settingsView.js"},
    "/api/settings/pipeline-plan-preview": {"settingsView.js"},
    "/api/settings/preview-patch": {"settingsView.js"},
    "/api/settings/save-patch": {"settingsView.js"},
    "/api/settings/reload": {"settingsView.js"},
}
REPAIR_RECONCILE_ROUTE_TERMS = ("repair", "reconcile", "reconciliation")
ALLOWED_TAURI_EVENT_BRIDGE = "tauriLifecycleBridge.js"


def _asset_sources() -> dict[str, str]:
    return {path.name: path.read_text(encoding="utf-8") for path in sorted(ASSET_ROOT.glob("*.js"))}


def _contract_post_routes() -> set[str]:
    return {
        str(route["path"])
        for route in LOCAL_API_ROUTE_CONTRACT
        if str(route.get("method", "")).upper() == "POST"
    }


def _literal_api_post_owners() -> dict[str, set[str]]:
    owners: dict[str, set[str]] = defaultdict(set)
    for name, source in _asset_sources().items():
        if name == "apiClient.js":
            continue
        for match in API_POST_LITERAL_RE.finditer(source):
            owners[match.group("route")].add(name)
    return dict(owners)


def _payload_for_route(asset_name: str, route: str) -> str:
    source = _asset_sources()[asset_name]
    pattern = re.compile(
        r"apiPost\s*\(\s*[\"']"
        + re.escape(route)
        + r"[\"']\s*,\s*(?P<payload>\{.*?\})\s*(?:,\s*\{.*?\})?\s*\)",
        flags=re.DOTALL,
    )
    match = pattern.search(source)
    if not match:
        raise AssertionError(f"Could not find payload for {route} in {asset_name}")
    return match.group("payload")


class WebViewFrontendMutationBoundaryTests(unittest.TestCase):
    def test_api_post_calls_are_literal_documented_command_routes(self) -> None:
        contract_post_routes = _contract_post_routes()
        unexpected: list[str] = []

        for name, source in _asset_sources().items():
            if name == "apiClient.js":
                continue
            literal_matches = list(API_POST_LITERAL_RE.finditer(source))
            all_calls = list(API_POST_CALL_RE.finditer(source))
            if len(literal_matches) != len(all_calls):
                unexpected.append(f"{name}: apiPost call must use a literal documented route")
                continue
            for match in literal_matches:
                route = match.group("route")
                if route not in contract_post_routes:
                    unexpected.append(f"{name}: {route} is not in LOCAL_API_ROUTE_CONTRACT")

        self.assertEqual(unexpected, [])

    def test_api_post_command_ownership_stays_page_specific(self) -> None:
        self.assertEqual(_literal_api_post_owners(), EXPECTED_API_POST_OWNERS)

    def test_ui_preferences_sync_stays_allowlisted_and_runs_before_layout_init(self) -> None:
        app_js = _asset_sources()["app.js"]

        self.assertIn('const UI_PREFERENCES_ROUTE = "/api/ui-preferences";', app_js)
        self.assertIn("const UI_PREFERENCE_KEY_RE = /^mediapipeline[-.]", app_js)
        self.assertIn("let uiPreferenceSyncPending = false;", app_js)
        self.assertIn('bootstrap.shellSurface || bootstrap.shell_surface || "webview"', app_js)
        self.assertIn('if (surface !== "tauri" && Object.keys(local).length)', app_js)
        self.assertIn("localStorage.removeItem(key)", app_js)
        self.assertIn("uiPreferenceSyncPending = true;", app_js)
        self.assertIn("await restoreSharedUiPreferences();", app_js)
        self.assertIn("installSharedUiPreferenceStorageSync();", app_js)
        self.assertIn("startSharedUiPreferenceRemoteRefresh();", app_js)
        self.assertIn("function applySharedUiPreferenceRuntimeState()", app_js)
        self.assertIn("function applyStoredLayoutPreferences()", app_js)
        self.assertLess(
            app_js.index("await restoreSharedUiPreferences();"),
            app_js.index("initLayoutManager();"),
        )
        self.assertLess(
            app_js.index("initCompletedTabNav();"),
            app_js.index("installSharedUiPreferenceStorageSync();"),
        )
        self.assertIn('const result = await apiPost("/api/ui-preferences", payload', app_js)
        self.assertIn("if (result && result.ok === false)", app_js)

    def test_shell_open_routes_submit_backend_selector_keys_not_raw_paths(self) -> None:
        specs = {
            "/api/diagnostics/open": ("diagnosticsView.js", {"target"}),
            "/api/queue/open": ("queueView.js", {"row_key", "row_scope", "target"}),
            "/api/completed/open": ("completedView.js", {"row_key", "target"}),
            "/api/pending-publish/open": ("pendingPublishView.diagnostics.js", {"row_key", "target"}),
        }
        forbidden_path_keys = {
            "path",
            "paths",
            "source",
            "source_path",
            "output_path",
            "folder",
            "file",
            "local_file",
            "destination",
            "destination_folder",
            "manifest",
        }

        for route, (asset_name, required_keys) in specs.items():
            payload = _payload_for_route(asset_name, route)
            for key in required_keys:
                self.assertRegex(
                    payload,
                    rf"\b{re.escape(key)}(?:\s*:|[\s,}}])",
                    f"{route} missing selector key {key}",
                )
            for key in forbidden_path_keys:
                self.assertNotRegex(
                    payload,
                    rf"\b{re.escape(key)}\s*:",
                    f"{route} in {asset_name} must not submit raw path key {key}",
                )

    def test_write_routes_keep_explicit_confirmation_payloads(self) -> None:
        self.assertIn("confirm_apply = true", _asset_sources()["renameView.js"])
        self.assertIn('apiPost("/api/rename/apply", request)', _asset_sources()["renameView.js"])
        reports_view_js = _asset_sources()["reportsView.js"]
        self.assertIn('apiPost("/api/failures/clear", payload)', reports_view_js)
        self.assertIn('const apiScope = scope === "all" ? "all_markers" : scope;', reports_view_js)
        self.assertIn("scope: request.scope", reports_view_js)
        self.assertIn("if (!request.all_markers) payload.marker_paths = request.marker_paths;", reports_view_js)
        self.assertIn("confirm_clear: !dryRun", reports_view_js)
        self.assertIn('apiPost("/api/settings/save-patch", { changes, ...requestExtras, confirm_save: true })', _asset_sources()["settingsView.js"])
        self.assertIn('apiPost("/api/schedule/save", { ...request, confirm_save: true })', _asset_sources()["scheduleView.js"])
        completed_js = _asset_sources()["completedView.js"]
        self.assertIn("const request = { confirm_promote: true };", completed_js)
        self.assertIn("if (selectedRowKeys.length) request.row_keys = selectedRowKeys;", completed_js)
        self.assertIn('apiPost("/api/final-library-promotion/promote-queue", request)', completed_js)

    def test_settings_save_warns_active_runtime_keeps_startup_config(self) -> None:
        settings_view = _asset_sources()["settingsView.js"]
        settings_wizard = _asset_sources()["settingsWizard.js"]
        for token in (
            "function settingsRuntimeRestartConfirmationLine",
            "function settingsRuntimeRestartNoticeLines",
            "Running pipeline/audit/rerun work keeps the settings loaded when it started.",
            "Restarting the Tauri shell is not required when reload succeeds.",
            "maybeShowSettingsRuntimeRestartNotice(result)",
        ):
            self.assertIn(token, settings_view)
        self.assertIn("settingsRuntimeRestartConfirmationLine", settings_wizard)
        self.assertIn("settingsRuntimeRestartNoticeLines(result)", settings_wizard)
        self.assertIn("maybeShowSettingsRuntimeRestartNotice?.(result)", settings_wizard)

    def test_settings_path_browse_is_allowlisted_staging_only(self) -> None:
        payload = _payload_for_route("settingsView.js", "/api/settings/browse-path")
        self.assertIn("setting_key: settingKey", payload)
        self.assertIn('selection_mode: "folder"', payload)
        self.assertIn("initial_path: initialPath", payload)
        self.assertNotIn("confirm_save", payload)
        browse_contract = next(route for route in LOCAL_API_ROUTE_CONTRACT if route["path"] == "/api/settings/browse-path")
        self.assertEqual(browse_contract["effect"], "shell-dialog")
        self.assertEqual(browse_contract["allowed_selection_modes"], ["folder"])
        self.assertEqual(
            browse_contract["allowed_setting_keys"],
            [
                "SourceMovies",
                "SourceTV",
                "Outsource",
                "LocalBase",
                "FinalLibraryPromotionRuleSourceRoot",
                "FinalLibraryPromotionRuleDestinationRoot",
            ],
        )
        self.assertIn("staging only", browse_contract["purpose"])
        self.assertIn("touch media files", browse_contract["purpose"])

    def test_settings_pipeline_plan_preview_is_non_mutating(self) -> None:
        payload = _payload_for_route("settingsView.js", "/api/settings/pipeline-plan-preview")
        self.assertIn("source_media: sourceMedia", payload)
        self.assertIn("changes: patchRequest.changes", payload)
        self.assertIn("remove_keys: patchRequest.removeKeys", payload)
        self.assertNotIn("confirm_save", payload)

        preview_contract = next(route for route in LOCAL_API_ROUTE_CONTRACT if route["path"] == "/api/settings/pipeline-plan-preview")
        self.assertEqual(preview_contract["effect"], "none")
        self.assertEqual(preview_contract["data_schema"], "pipeline_plan.v1")
        self.assertIn("without probing paths", preview_contract["purpose"])
        self.assertIn("saving config", preview_contract["purpose"])
        self.assertIn("touching media files", preview_contract["purpose"])

    def test_repair_reconcile_mutation_remains_design_only_and_not_webview_callable(self) -> None:
        payload = local_api_contract_payload(app_version="v5-test", host="127.0.0.1")
        summary = payload["repair_reconcile_summary"]

        self.assertEqual(summary["status"], "design_only_no_mutation_routes")
        self.assertFalse(summary["mutation_enabled"])
        self.assertFalse(summary["frontend_allowed"])
        self.assertIn("dry-run diffs", summary["safe_next_step"])
        self.assertIn("atomic journals", summary["safe_next_step"])
        for contract in payload["repair_reconcile_contracts"]:
            with self.subTest(contract=contract["key"]):
                self.assertEqual(contract["dry_run_contract"]["effect"], "none")
                self.assertIn("dry_run_only", contract["dry_run_contract"]["required_result_fields"])
                self.assertIn("would_not_touch", contract["dry_run_contract"]["required_result_fields"])
                self.assertTrue(contract["rollback_contract"]["required_for_mutation_route"])
                self.assertTrue(contract["rollback_contract"]["journal_required"])
                self.assertEqual(contract["source_file_policy"]["source_media_mutation"], "forbidden")
                self.assertTrue(any("API_ROUTE_INVENTORY.md" in gate for gate in contract["route_exposure_gates"]))

        callable_routes = [
            f"{route.get('method')} {route.get('path')} ({route.get('effect')})"
            for route in LOCAL_API_ROUTE_CONTRACT
            if str(route.get("method", "")).upper() == "POST"
            and any(term in str(route.get("path", "")).lower() for term in REPAIR_RECONCILE_ROUTE_TERMS)
        ]
        self.assertEqual(callable_routes, [])

        read_only_reconciliation = [
            route
            for route in LOCAL_API_ROUTE_CONTRACT
            if any(term in str(route.get("path", "")).lower() for term in REPAIR_RECONCILE_ROUTE_TERMS)
        ]
        self.assertTrue(read_only_reconciliation)
        for route in read_only_reconciliation:
            with self.subTest(route=route["path"]):
                self.assertEqual(route["method"], "GET")
                self.assertEqual(route["effect"], "none")

        post_repair_routes = [
            route
            for route in _literal_api_post_owners()
            if any(term in route.lower() for term in REPAIR_RECONCILE_ROUTE_TERMS)
        ]
        self.assertEqual(post_repair_routes, [])

        contract_view = _asset_sources()["contractView.js"]
        for snippet in [
            "Repair/reconcile boundary",
            "mutation enabled",
            "frontend allowed",
            "Implement backend dry-run diffs and atomic journals before adding any repair/reconcile command routes.",
            "repair/reconcile commands are not allowed until the backend owns dry-run proof, atomic write/rollback, and command-journal evidence.",
            "Dry-run contract fields",
            "Rollback journal fields",
            "Source policy: source media mutation=",
            "Route exposure gates",
        ]:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, contract_view)

    def test_contract_view_warns_for_high_risk_contract_effect_rows(self) -> None:
        route_effects = {str(route["effect"]) for route in LOCAL_API_ROUTE_CONTRACT}
        self.assertIn("filesystem-mutation", route_effects)
        self.assertIn("backend-lifecycle", route_effects)

        contract_view = _asset_sources()["contractView.js"]
        match = re.search(
            r"function contractRouteStatus\(route\) \{(?P<body>.*?)\n  \}",
            contract_view,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match)
        status_body = match.group("body")
        for effect_fragment in ("process", "control", "write", "mutation", "lifecycle"):
            with self.subTest(effect_fragment=effect_fragment):
                self.assertIn(f'effect.includes("{effect_fragment}")', status_body)

    def test_frontend_media_policy_risk_helpers_stay_advisory_not_authoritative(self) -> None:
        sources = _asset_sources()
        settings_view = sources["settingsView.js"]
        settings_metadata = sources["settingsMetadata.js"]
        launch_risk = sources["launchView.risk.js"]

        for snippet in [
            "Frontend advisory only",
            "backend Preview Patch and Save Patch remain",
            "source-deletion acceptance",
            "PSD1 writes",
            "settingsBackendPolicyImpact",
        ]:
            with self.subTest(asset="settingsView.js", snippet=snippet):
                self.assertIn(snippet, settings_view)

        self.assertIn("UI arrays are display/order bindings", settings_metadata)
        self.assertIn("Backend field_definitions owns labels, options, defaults, constraints, validation, and persistence", settings_metadata)

        for snippet in [
            "Frontend advisory only",
            "backend launch validation remains authoritative",
            "queue scope",
            "route safety",
            "publish/drain safety",
            "source-deletion policy",
            "policy_impact.launch_risk_handoff is preferred",
        ]:
            with self.subTest(asset="launchView.risk.js", snippet=snippet):
                self.assertIn(snippet, launch_risk)

    def test_only_api_client_owns_fetch_and_no_direct_process_or_filesystem_apis_exist(self) -> None:
        forbidden_patterns = {
            r"\brequire\s*\(": "CommonJS require",
            r"\bimport\s*\(": "dynamic import",
            r"\bXMLHttpRequest\b": "raw XMLHttpRequest",
            r"\bchild_process\b": "Node child_process",
            r"\bActiveXObject\b": "ActiveX shell access",
            r"\bShell\.Application\b": "Windows shell automation",
            r"\bWScript\.Shell\b": "Windows scripting shell",
            r"\bDeno\.": "Deno filesystem/process APIs",
            r"\b__TAURI__\b": "direct Tauri bridge access",
            r"@tauri-apps/api": "direct Tauri API import",
        }

        failures: list[str] = []
        for name, source in _asset_sources().items():
            if name != "apiClient.js" and re.search(r"\bfetch\s*\(", source):
                failures.append(f"{name}: fetch must stay centralized in apiClient.js")
            for pattern, label in forbidden_patterns.items():
                if label == "direct Tauri bridge access" and name == ALLOWED_TAURI_EVENT_BRIDGE:
                    continue
                if re.search(pattern, source):
                    failures.append(f"{name}: direct frontend {label} use is forbidden")

        self.assertEqual(failures, [])

    def test_tauri_lifecycle_bridge_is_read_only_event_listener(self) -> None:
        sources = _asset_sources()
        bridge = sources[ALLOWED_TAURI_EVENT_BRIDGE]
        app = sources["app.js"]

        for snippet in [
            "mediapipeline://backend-lifecycle",
            "mediapipeline:backend-lifecycle",
            "window.__TAURI__",
            "eventApi.listen",
            "window.dispatchEvent(new CustomEvent",
        ]:
            with self.subTest(asset=ALLOWED_TAURI_EVENT_BRIDGE, snippet=snippet):
                self.assertIn(snippet, bridge)

        for forbidden in [
            "apiPost(",
            "fetch(",
            "invoke",
            "shell",
            "child_process",
            "filesystem",
            "openPath",
            "writeTextFile",
            "remove",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, bridge)

        for snippet in [
            'window.addEventListener("mediapipeline:backend-lifecycle", handleTauriBackendLifecycleEvent)',
            "tauri-lifecycle-alert",
            "Open Diagnostics before starting, draining, saving, renaming, publishing, or closing.",
            "Recovery: refresh once, then inspect Diagnostics run logs",
        ]:
            with self.subTest(asset="app.js", snippet=snippet):
                self.assertIn(snippet, app)


if __name__ == "__main__":
    unittest.main()
