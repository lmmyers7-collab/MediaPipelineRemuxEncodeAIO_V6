from __future__ import annotations

import re
import sys
import unittest
from collections import defaultdict
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.contract import LOCAL_API_ROUTE_CONTRACT
from mediapipeline.desktop.api.contract_payload import local_api_contract_payload


REPO_ROOT = find_repo_root(Path(__file__))
ASSET_ROOT = REPO_ROOT / "apps" / "desktop" / "webview" / "static" / "assets"
HOME_PARTIAL = REPO_ROOT / "apps" / "desktop" / "webview" / "static" / "partials" / "page-home.html"
LAUNCH_PARTIAL = REPO_ROOT / "apps" / "desktop" / "webview" / "static" / "partials" / "page-launch.html"
PENDING_PARTIAL = REPO_ROOT / "apps" / "desktop" / "webview" / "static" / "partials" / "page-pending.html"
DIAGNOSTICS_PARTIAL = REPO_ROOT / "apps" / "desktop" / "webview" / "static" / "partials" / "page-diagnostics.html"
QUEUE_PARTIAL = REPO_ROOT / "apps" / "desktop" / "webview" / "static" / "partials" / "page-queue.html"
SETTINGS_PARTIAL = REPO_ROOT / "apps" / "desktop" / "webview" / "static" / "partials" / "page-settings.html"
API_POST_LITERAL_RE = re.compile(
    r"(?<![\w$])(?:\w+\.)?apiPost(?:Local)?\s*\(\s*(?P<quote>[\"'])(?P<route>/api/[^\"']+)(?P=quote)"
)
API_POST_CALL_RE = re.compile(r"(?<!function\s)(?<![\w$])(?:\w+\.)?apiPost(?:Local)?\s*\(")

EXPECTED_API_POST_OWNERS: dict[str, set[str]] = {
    "/api/backend/shutdown": {"app.js"},
    "/api/ui-preferences": {"app.js"},
    "/api/pipeline/control": {"launchView.js"},
    "/api/pipeline/browse-file": {"launchView.js"},
    "/api/pipeline/start": {"launchView.js"},
    "/api/audit/start": {"launchView.js", "reportsView.js"},
    "/api/rerun/start": {"launchView.js"},
    "/api/audit/score-policy": {"launchView.js", "reportsView.js"},
    "/api/audit/ignore": {"launchView.js", "reportsView.js"},
    "/api/audit/export-rerun-csv": {"launchView.js", "reportsView.js"},
    "/api/completed/open": {"completed/openActions.js"},
    "/api/final-library-promotion/promote-queue": {"completed/promotionCommands.js"},
    "/api/final-library-promotion/pause": {"completed/promotionCommands.js"},
    "/api/final-library-promotion/resume": {"completed/promotionCommands.js"},
    "/api/maintenance/release-dry-run": {"maintenanceView.js"},
    "/api/maintenance/release-build": {"maintenanceView.js"},
    "/api/maintenance/completed-backfill-dry-run": {"maintenanceView.js"},
    "/api/maintenance/dependency-atlas": {"maintenanceView.js"},
    "/api/maintenance/dependency-atlas/open-folder": {"maintenanceView.js"},
    "/api/sample-validation/preview": {"crossPageContextView.sampleValidation.js"},
    "/api/sample-validation/append": {"crossPageContextView.sampleValidation.js"},
    "/api/diagnostics/open": {"diagnosticsView.js"},
    "/api/diagnostics/tdarr-matrix-audit": {"diagnosticsView.js"},
    "/api/diagnostics/tdarr-matrix/evidence/open": {"diagnosticsView.js"},
    "/api/diagnostics/tdarr-matrix/rerun": {"diagnosticsView.js"},
    "/api/pending-publish/open": {"pendingPublishView.diagnostics.js"},
    "/api/pending-publish/recovery-plan": {"pendingPublishView.recovery.js"},
    "/api/queue/open": {"queue/openActions.js"},
    "/api/queue/scan": {"queueView.js"},
    "/api/queue/priority": {"queueView.js"},
    "/api/queue/strategy": {"queueView.js"},
    "/api/queue/file-overrides": {"queue/fileOverrides.drawer.api.js"},
    "/api/queue/file-overrides/route-preview": {"queue/fileOverrides.routePreview.js"},
    "/api/queue/file-overrides/series-preview": {"queue/fileOverrides.drawer.series.js"},
    "/api/queue/file-overrides/series-apply": {"queue/fileOverrides.drawer.series.js"},
    "/api/failures/clear": {"reportsView.js"},
    "/api/rename/apply": {"renameView.js"},
    "/api/rename/browse": {"renameView.js"},
    "/api/rename/preview": {"renameView.js"},
    "/api/schedule/preview": {"scheduleView.js"},
    "/api/schedule/save": {"scheduleView.js"},
    "/api/settings/validate": {"settingsView.js"},
    "/api/settings/browse-path": {"settingsView.js"},
    "/api/settings/preview-patch": {"settingsView.js"},
    "/api/settings/save-patch": {"settingsView.js"},
    "/api/settings/reload": {"settingsView.js"},
    "/api/settings/wizard/validate-paths": {"settingsWizard.js"},
    "/api/settings/wizard/validate-tools": {"settingsWizard.js"},
    "/api/settings/wizard/probe-hardware": {"settingsWizard.js"},
    "/api/settings/wizard/validate-workers": {"settingsWizard.js"},
    "/api/settings/wizard/preview": {"settingsWizard.js"},
    "/api/settings/wizard/save": {"settingsWizard.js"},
    "/api/network/worker/test-connection": {"networkView.js"},
    "/api/network/coordinator/join-blob": {"networkView.js"},
    "/api/network/worker/join-cluster": {"networkView.js"},
}
REPAIR_RECONCILE_ROUTE_TERMS = ("repair", "reconcile", "reconciliation")
ALLOWED_TAURI_EVENT_BRIDGE = "tauriLifecycleBridge.js"


def _asset_sources() -> dict[str, str]:
    return {
        path.relative_to(ASSET_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(ASSET_ROOT.rglob("*.js"))
    }


def _launch_risk_source(sources: dict[str, str] | None = None) -> str:
    loaded_sources = sources if sources is not None else _asset_sources()
    return "\n".join(
        loaded_sources[name]
        for name in [
            "launch/risk/settingsAccess.js",
            "launch/risk/mediaPolicyValues.js",
            "launch/risk/riskRows.js",
            "launch/risk/policyPatch.js",
            "launch/risk/policyBoundary.js",
            "launchView.risk.js",
        ]
    )


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
        r"(?:\w+\.)?apiPost(?:Local)?\s*\(\s*[\"']"
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
                if (
                    name == "networkView.js"
                    and len(all_calls) - len(literal_matches) == 1
                    and "function postNetworkLifecycleRoute" in source
                    and "apiPost(route, request)" in source
                ):
                    continue
                unexpected.append(f"{name}: apiPost call must use a literal documented route")
                continue
            for match in literal_matches:
                route = match.group("route")
                if route not in contract_post_routes:
                    unexpected.append(f"{name}: {route} is not in LOCAL_API_ROUTE_CONTRACT")

        self.assertEqual(unexpected, [])

    def test_api_post_command_ownership_stays_page_specific(self) -> None:
        self.assertEqual(_literal_api_post_owners(), EXPECTED_API_POST_OWNERS)

    def test_network_lifecycle_dispatch_uses_backend_contract_routes_and_confirmation_prompt(self) -> None:
        source = _asset_sources()["networkView.js"]
        lifecycle_paths = (
            "/api/network/coordinator/start-dry-run",
            "/api/network/coordinator/stop-dry-run",
            "/api/network/worker/start-dry-run",
            "/api/network/worker/stop-dry-run",
            "/api/network/coordinator/start",
            "/api/network/coordinator/stop",
            "/api/network/worker/start",
            "/api/network/worker/stop",
        )

        self.assertIn("function networkLifecycleRouteRow", source)
        self.assertIn("route?.network_lifecycle", source)
        self.assertIn("function networkLifecycleRoutePath", source)
        self.assertIn("apiPost(route, request)", source)
        self.assertIn("function confirmNetworkLifecycleCommand", source)
        self.assertIn("network-lifecycle-confirm-dialog", source)
        self.assertIn("Confirmed lifecycle command was cancelled", source)
        self.assertIn("confirm_start", source)
        self.assertIn("confirm_stop", source)
        for path in lifecycle_paths:
            with self.subTest(path=path):
                self.assertNotIn(path, source)

    def test_diagnostics_does_not_own_pipeline_control_mutations(self) -> None:
        diagnostics_view = _asset_sources()["diagnosticsView.js"]
        diagnostics_html = DIAGNOSTICS_PARTIAL.read_text(encoding="utf-8")

        self.assertNotIn("/api/pipeline/control", diagnostics_view)
        self.assertNotIn("diagnostics-force-reset", diagnostics_view)
        self.assertNotIn("diagnostics-force-reset", diagnostics_html)
        self.assertIn(
            "Diagnostics is read-only. If evidence shows stuck progress",
            diagnostics_html,
        )

    def test_tdarr_matrix_findings_render_in_diagnostics_table(self) -> None:
        diagnostics_view = _asset_sources()["diagnosticsView.js"]
        diagnostics_html = DIAGNOSTICS_PARTIAL.read_text(encoding="utf-8")

        self.assertIn('id="tdarr-matrix-audit-findings-rows"', diagnostics_html)
        self.assertIn('id="tdarr-matrix-audit-findings-status"', diagnostics_html)
        self.assertIn('id="tdarr-matrix-audit-filter"', diagnostics_html)
        self.assertIn('id="tdarr-matrix-audit-bucket-rows"', diagnostics_html)
        self.assertIn('id="tdarr-matrix-run-compare-rows"', diagnostics_html)
        self.assertIn('id="tdarr-matrix-audit-rerun-selected"', diagnostics_html)
        self.assertIn('id="tdarr-matrix-proof-pack-rows"', diagnostics_html)
        self.assertIn('id="tdarr-matrix-proof-pack-status"', diagnostics_html)
        self.assertIn('data-tdarr-matrix-audit-action="prepare-proof-pack"', diagnostics_html)
        self.assertIn('data-tdarr-matrix-audit-action="smoke-pack"', diagnostics_html)
        self.assertIn('data-tdarr-matrix-audit-action="proof-pack"', diagnostics_html)
        self.assertIn('data-tdarr-matrix-audit-action="cleanup-plan"', diagnostics_html)
        self.assertIn('data-tdarr-matrix-audit-action="cleanup-archive"', diagnostics_html)
        self.assertIn('data-tdarr-matrix-audit-action="cleanup-delete"', diagnostics_html)
        self.assertNotIn('data-tdarr-matrix-audit-action="full"', diagnostics_html)
        self.assertIn("function renderTdarrMatrixAuditFindings", diagnostics_view)
        self.assertIn("function renderTdarrMatrixBucketCoverage", diagnostics_view)
        self.assertIn("function renderTdarrMatrixRunComparison", diagnostics_view)
        self.assertIn("function renderTdarrMatrixProofPackRows", diagnostics_view)
        self.assertIn("function requestTdarrMatrixEvidenceOpen", diagnostics_view)
        self.assertIn("function requestTdarrMatrixRerun", diagnostics_view)
        self.assertIn('"proof-pack": "Proof Pack"', diagnostics_view)
        self.assertIn('"cleanup-delete": "Delete Verified Full Matrix"', diagnostics_view)
        self.assertNotIn('full: "Run 100% Matrix"', diagnostics_view)
        self.assertIn('checkbox.addEventListener("click"', diagnostics_view)
        self.assertIn('selectCell.addEventListener("click"', diagnostics_view)
        self.assertIn("/api/diagnostics/tdarr-matrix/latest", diagnostics_view)
        self.assertIn("/api/diagnostics/tdarr-matrix/compare", diagnostics_view)
        self.assertIn("findings_preview", diagnostics_view)
        self.assertIn("findings_preview_truncated", diagnostics_view)
        self.assertIn("tdarr-matrix-audit-findings-rows", diagnostics_view)
        self.assertIn("tdarr-matrix-audit-findings-status", diagnostics_view)

    def test_home_does_not_surface_tdarr_matrix_activity(self) -> None:
        home_html = HOME_PARTIAL.read_text(encoding="utf-8")
        app_js = _asset_sources()["app.js"]
        home_js = _asset_sources()["app/home.js"]
        home_readiness_js = _asset_sources()["app/homeReadiness.js"]

        self.assertNotIn('id="home-tdarr-matrix-status"', home_html)
        self.assertNotIn('id="home-tdarr-matrix-detail"', home_html)
        self.assertNotIn('id="home-tdarr-matrix-panel-status"', home_html)
        self.assertNotIn('id="home-tdarr-matrix-progress-bars"', home_html)
        self.assertNotIn('id="home-tdarr-matrix-summary"', home_html)
        self.assertNotIn("data-tdarr-matrix-audit-action", home_html)
        self.assertNotIn("function shouldRefreshTdarrMatrix", app_js)
        self.assertNotIn('refreshGet("/api/diagnostics/tdarr-matrix/latest?finding_limit=0"', app_js)
        self.assertNotIn("renderHomeTdarrMatrixStatus", home_js)
        self.assertNotIn("homeTdarrMatrixStatusModel", home_js)
        self.assertNotIn("homeTdarrMatrixProgressBars", home_js)
        self.assertNotIn("renderHomeTdarrMatrixStatus", home_readiness_js)
        self.assertNotIn('apiPost("/api/diagnostics/tdarr-matrix', app_js)

    def test_live_run_progress_surfaces_are_read_only_shared_renderer(self) -> None:
        home_html = HOME_PARTIAL.read_text(encoding="utf-8")
        launch_html = LAUNCH_PARTIAL.read_text(encoding="utf-8")
        pending_html = PENDING_PARTIAL.read_text(encoding="utf-8")
        diagnostics_html = DIAGNOSTICS_PARTIAL.read_text(encoding="utf-8")
        app_js = _asset_sources()["app.js"]
        progress_js = _asset_sources()["progressView.js"]
        pending_js = _asset_sources()["pendingPublishView.js"]

        for html, prefix in [
            (home_html, "home"),
            (launch_html, "launch"),
            (pending_html, "pending"),
            (diagnostics_html, "diagnostics"),
        ]:
            self.assertIn(f'id="{prefix}-live-run-status"', html)
            self.assertIn(f'id="{prefix}-live-run-strip"', html)
            self.assertIn('class="live-run-strip"', html)

        self.assertIn("function renderLiveRunStrip", progress_js)
        self.assertIn("function liveRunStripItems", progress_js)
        self.assertIn("progressBarForStableDisplay", progress_js)
        self.assertIn('track.setAttribute("aria-valuetext", progressBarStatusLabel(bar));', progress_js)
        self.assertIn("renderLiveRunStrip?.({", app_js)
        self.assertIn('id="pending-drain-progress-bars"', pending_html)
        self.assertIn("function renderPendingDrainProgress", pending_js)
        self.assertIn('"pending_drain"', pending_js)
        self.assertNotIn('apiPost("/api/progress', progress_js)

    def test_ui_preferences_sync_stays_allowlisted_and_runs_before_layout_init(self) -> None:
        app_js = _asset_sources()["app.js"]

        self.assertIn('const UI_PREFERENCES_ROUTE = "/api/ui-preferences";', app_js)
        self.assertIn("const UI_PREFERENCE_KEY_RE = /^mediapipeline[-.]", app_js)
        self.assertIn("let uiPreferenceSyncPending = false;", app_js)
        self.assertIn("let uiPreferenceLocalDirty = false;", app_js)
        self.assertIn('bootstrap.shellSurface || bootstrap.shell_surface || "webview"', app_js)
        self.assertIn('if (surface !== "tauri" && Object.keys(local).length)', app_js)
        self.assertIn("localStorage.removeItem(key)", app_js)
        self.assertIn("uiPreferenceSyncPending = true;", app_js)
        self.assertIn("uiPreferenceLocalDirty = true;", app_js)
        self.assertIn("function hasPendingSharedUiPreferenceWrite()", app_js)
        self.assertIn("hasPendingSharedUiPreferenceWrite() && JSON.stringify(remoteStorage) !== localSerialized", app_js)
        self.assertLess(
            app_js.index("function hasPendingSharedUiPreferenceWrite()"),
            app_js.index("async function restoreSharedUiPreferences"),
        )
        self.assertIn("await restoreSharedUiPreferences();", app_js)
        self.assertIn("installSharedUiPreferenceStorageSync();", app_js)
        self.assertIn("startSharedUiPreferenceRemoteRefresh();", app_js)
        self.assertIn("function applySharedUiPreferenceRuntimeState()", app_js)
        self.assertIn("function applyStoredLayoutPreferences()", app_js)
        install_index = app_js.index("installSharedUiPreferenceStorageSync();")
        self.assertLess(app_js.index("await restoreSharedUiPreferences();"), install_index)
        for startup_call in [
            "initNavigation();",
            "initLayoutManager();",
            "initAdvancedToggle();",
            "initEvidenceToggle();",
            "initThemeToggle();",
            "initSettingsTabNav();",
            "initDiagnosticsTabNav();",
            "initCompletedTabNav();",
            "startSharedUiPreferenceRemoteRefresh();",
        ]:
            with self.subTest(startup_call=startup_call):
                self.assertLess(install_index, app_js.index(startup_call))
        self.assertIn('const result = await apiPost("/api/ui-preferences", payload', app_js)
        self.assertIn("if (result && result.ok === false)", app_js)

    def test_shell_open_routes_submit_backend_selector_keys_not_raw_paths(self) -> None:
        specs = {
            "/api/diagnostics/open": ("diagnosticsView.js", {"target"}),
            "/api/diagnostics/tdarr-matrix/evidence/open": ("diagnosticsView.js", {"run_id", "finding_key", "target"}),
            "/api/diagnostics/tdarr-matrix/rerun": ("diagnosticsView.js", {"source_run_id", "selection", "finding_keys"}),
            "/api/queue/open": ("queue/openActions.js", {"row_key", "row_scope", "target"}),
            "/api/completed/open": ("completed/openActions.js", {"row_key", "target"}),
            "/api/pending-publish/open": ("pendingPublishView.diagnostics.js", {"row_key", "target"}),
            "/api/maintenance/dependency-atlas/open-folder": ("maintenanceView.js", set()),
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
            "generated_path",
            "source_path",
            "output_path",
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
        self.assertIn('apiPostLocal("/api/settings/wizard/save", { wizard: collectWizardPayload(), confirm_save: true })', _asset_sources()["settingsWizard.js"])
        self.assertIn('apiPost("/api/schedule/save", { ...request, confirm_save: true })', _asset_sources()["scheduleView.js"])
        maintenance_js = _asset_sources()["maintenanceView.js"]
        self.assertIn("confirm_create: true", maintenance_js)
        self.assertIn("include_tauri_preview_binary", maintenance_js)
        completed_js = _asset_sources()["completed/promotionCommands.js"]
        self.assertIn("const request = { confirm_promote: true };", completed_js)
        self.assertIn("if (selectedRowKeys.length) request.row_keys = selectedRowKeys;", completed_js)
        self.assertIn('apiPost("/api/final-library-promotion/promote-queue", request)', completed_js)

    def test_queue_loaded_priority_copy_does_not_imply_launch_scope(self) -> None:
        queue_html = QUEUE_PARTIAL.read_text(encoding="utf-8")
        queue_view = _asset_sources()["queueView.js"]

        for snippet in [
            "All Loaded Movies",
            "All Loaded TV",
            "loaded queue rows regardless of display filters or render cap",
            "They do not define Launch scope",
            "Save Loaded Backend Order",
            "save loaded backend rows within their backend phase",
            "display filters and render caps do not define Launch scope",
        ]:
            with self.subTest(asset="page-queue.html", snippet=snippet):
                self.assertIn(snippet, queue_html)
        for snippet in [
            "Loaded queue rows:",
            "Current display-filter matches for",
            "This loaded-row action ignores display filters and the table render cap",
            "Backend Launch scope remains unchanged and is still decided by Launch routes.",
            "does not touch source, scratch, output, or rename files",
            "Saving loaded backend manual positions",
            "Saved loaded backend queue order to the backend manifest",
            "Display filters and render caps did not define the saved scope.",
        ]:
            with self.subTest(asset="queueView.js", snippet=snippet):
                self.assertIn(snippet, queue_view)
        self.assertNotIn("Save Order", queue_html)
        self.assertNotIn("current table order", queue_html + queue_view)
        self.assertNotIn("Promote all visible Movie", queue_html + queue_view)
        self.assertNotIn("visible rows to High priority", queue_html + queue_view)

    def test_rename_filter_staging_uses_settings_patch_not_direct_psd1_save(self) -> None:
        rename_view = _asset_sources()["renameView.js"]
        settings_html = SETTINGS_PARTIAL.read_text(encoding="utf-8")

        for snippet in [
            "Stage Rename Filter Patch",
            "Settings Changes JSON",
            "Browser storage is local draft recovery only and does not persist PSD1 settings",
            "Preview Patch",
            "Save Settings",
            "Guided setup stages the same PSD1-backed settings used by the manual editor.",
            "Preview and save go through backend validation",
        ]:
            with self.subTest(asset="page-settings.html", snippet=snippet):
                self.assertIn(snippet, settings_html)
        self.assertNotIn("Guided setup writes PSD1", settings_html)
        self.assertNotIn("validates locally", settings_html)
        for snippet in [
            "function stageRenameCleaningFilterPatch(changes)",
            "Rename filter patch staged into Settings Changes JSON; no backend save route was called.",
            "Next step: run Preview Patch, then Save Settings from Settings.",
            "Browser storage is local draft recovery only",
        ]:
            with self.subTest(asset="renameView.js", snippet=snippet):
                self.assertIn(snippet, rename_view)
        self.assertNotIn('/api/settings/preview-patch', rename_view)
        self.assertNotIn('/api/settings/save-patch', rename_view)

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

    def test_settings_pipeline_plan_preview_route_is_non_mutating_but_not_webview_callable(self) -> None:
        preview_contract = next(route for route in LOCAL_API_ROUTE_CONTRACT if route["path"] == "/api/settings/pipeline-plan-preview")
        self.assertEqual(preview_contract["effect"], "none")
        self.assertEqual(preview_contract["data_schema"], "pipeline_plan.v1")
        self.assertIn("without probing paths", preview_contract["purpose"])
        self.assertIn("saving config", preview_contract["purpose"])
        self.assertIn("touching media files", preview_contract["purpose"])
        self.assertNotIn("/api/settings/pipeline-plan-preview", _literal_api_post_owners())
        self.assertNotIn("/api/settings/pipeline-plan-preview", _asset_sources()["settingsView.js"])

    def test_library_route_map_frontend_is_read_only_evidence_navigation(self) -> None:
        sources = _asset_sources()
        route_map = sources["librariesRouteMap.js"]
        forbidden_routes = (
            "/api/pipeline/start",
            "/api/pipeline/control",
            "/api/pending-publish/recovery-plan",
            "/api/final-library-promotion/promote-queue",
            "/api/final-library-promotion/pause",
            "/api/final-library-promotion/resume",
            "/api/rename/apply",
            "/api/rename/preview",
            "/api/settings/save-patch",
            "/api/settings/preview-patch",
            "/api/settings/browse-path",
            "/api/queue/scan",
            "/api/queue/priority",
            "/api/queue/file-overrides",
            "/api/sample-validation/append",
        )

        self.assertIn("/api/libraries/route-map", route_map)
        self.assertIn("/api/libraries/route-map/trace", route_map)
        self.assertIn("/api/libraries/route-map/compare", route_map)
        self.assertIn("/api/libraries/route-map/validation", route_map)
        self.assertIn("data-library-route-navigate", route_map)
        self.assertIn("focusLibraryControl", route_map)
        self.assertNotIn("apiPost", route_map)
        for route in forbidden_routes:
            with self.subTest(route=route):
                self.assertNotIn(route, route_map)

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
        launch_risk = _launch_risk_source(sources)

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
            with self.subTest(asset="launch risk bundle", snippet=snippet):
                self.assertIn(snippet, launch_risk)

    def test_launch_staged_policy_boundary_includes_vobsub_drop_without_ocr(self) -> None:
        launch_risk = _launch_risk_source()
        match = re.search(
            r"function launchPolicyCandidatePosture\(area, candidate, changedCount\) \{(?P<body>.*?)\n  \}",
            launch_risk,
            flags=re.DOTALL,
        )
        self.assertIsNotNone(match)
        helper_body = match.group("body")

        self.assertIn("candidate.dropVobSub && !candidate.convertVobSub", helper_body)
        self.assertIn("candidate.dropVobSub", helper_body)
        self.assertIn("!candidate.convertVobSub", helper_body)

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
            "mediaPipelineTauriLifecycleBridge",
            "replayLatestBackendLifecycleEvent",
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
            "window.mediaPipelineTauriLifecycleBridge?.replayLatestBackendLifecycleEvent?.()",
            "tauri-lifecycle-alert",
            "Open Diagnostics before starting, draining, saving, renaming, publishing, or closing.",
            "Recovery: refresh once, then inspect Diagnostics run logs",
        ]:
            with self.subTest(asset="app.js", snippet=snippet):
                self.assertIn(snippet, app)


if __name__ == "__main__":
    unittest.main()
