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
API_POST_DISPATCH_LITERAL_RE = re.compile(
    r"\brequireApiPost\s*\([^)]*\)\s*\(\s*(?P<quote>[\"'])(?P<route>/api/[^\"']+)(?P=quote)"
)
API_POST_CALL_RE = re.compile(r"(?<!function\s)(?<![\w$])(?:\w+\.)?apiPost(?:Local)?\s*\(")
NETWORK_CHILD_ASSET_NAMES = (
    "network/configDiagnostics.js",
    "network/config.js",
    "network/queueProjection.js",
    "network/overviewTiles.js",
    "network/overviewModel.js",
    "network/lifecycleContract.js",
    "network/stateFiles.js",
    "network/readiness.js",
    "network/lifecycle.view.js",
    "network/status.js",
    "network/lifecycle.model.js",
    "network/lifecycle.results.js",
    "network/lifecycle.commands.js",
    "network/setup.commands.js",
    "network/settingsHandoff.js",
    "network/openHistory.js",
    "network/evidence.js",
    "network/workers.model.js",
    "network/workers.view.js",
    "network/roleDashboard.js",
    "network/rerunEvidence.js",
    "network/events.js",
)
NETWORK_ASSET_NAMES = (*NETWORK_CHILD_ASSET_NAMES, "networkView.js")
NETWORK_DYNAMIC_DISPATCH_ASSETS = {
    "networkView.js",
    "network/lifecycle.commands.js",
    "network/setup.commands.js",
}
SCHEDULE_ASSET_NAMES = (
    "schedule/watchFolder.js",
    "schedule/editor.js",
    "scheduleView.js",
)
DIAGNOSTICS_ASSET_NAMES = (
    "diagnosticsView.activejobs.js",
    "diagnosticsView.log.js",
    "diagnosticsView.investigation.js",
    "diagnostics/matrixConsole.js",
    "diagnostics/triage.js",
    "diagnostics/firstResponse.js",
    "diagnosticsView.js",
)
MAINTENANCE_ASSET_NAMES = (
    "maintenance/changeLedger.js",
    "maintenance/health.js",
    "maintenance/dryRunReadiness.js",
    "maintenance/releaseCommands.js",
    "maintenanceView.js",
)

EXPECTED_API_POST_OWNERS: dict[str, set[str]] = {
    "/api/backend/shutdown": {"app.js"},
    "/api/ui-preferences": {"app.js"},
    "/api/pipeline/control": {"launch/commandOrchestration.js"},
    "/api/pipeline/browse-file": {"launch/commandOrchestration.js"},
    "/api/pipeline/start": {"launch/commandOrchestration.js"},
    "/api/path-picker/browse": {"pathPicker.js"},
    "/api/audit/start": {"reports/auditCommands.js"},
    "/api/audit/stop": {"reports/auditCommands.js"},
    "/api/rerun/preview": {"queue/rerunApi.js"},
    "/api/rerun/network-preview": {"queue/rerunApi.js"},
    "/api/rerun/network/start-dry-run": {"queue/rerunApi.js"},
    "/api/rerun/network/start": {"queue/rerunApi.js"},
    "/api/rerun/start": {"queue/rerunApi.js"},
    "/api/rerun/control": {"queue/rerunApi.js"},
    "/api/rerun/continue": {"queue/rerunApi.js"},
    "/api/rerun/promote-dry-run": {"queue/rerunApi.js"},
    "/api/rerun/promote": {"queue/rerunApi.js"},
    "/api/audit/score-policy": {"reports/auditCommands.js"},
    "/api/audit/ignore": {"reports/auditCommands.js"},
    "/api/audit/sources": {"reports/auditCommands.js"},
    "/api/audit/sources/scan": {"reports/auditCommands.js"},
    "/api/audit/export-rerun-csv": {"reports/auditCommands.js"},
    "/api/rerun/open": {"queue/rerunApi.js"},
    "/api/completed/open": {"completed/openActions.js"},
    "/api/final-library-promotion/promote-queue": {"completed/promotionCommands.js"},
    "/api/final-library-promotion/pause": {"completed/promotionCommands.js"},
    "/api/final-library-promotion/resume": {"completed/promotionCommands.js"},
    "/api/maintenance/release-dry-run": {"maintenance/releaseCommands.js"},
    "/api/maintenance/release-build": {"maintenance/releaseCommands.js"},
    "/api/maintenance/completed-backfill-dry-run": {"maintenance/releaseCommands.js"},
    "/api/maintenance/dependency-atlas": {"maintenance/releaseCommands.js"},
    "/api/maintenance/dependency-atlas/open-folder": {"maintenance/releaseCommands.js"},
    "/api/maintenance/archive-state-journals": {"launch/commandOrchestration.js"},
    "/api/maintenance/support-export": {"recoverySupportView.js"},
    "/api/sample-validation/preview": {"crossPageContextView.sampleValidation.js"},
    "/api/sample-validation/append": {"crossPageContextView.sampleValidation.js"},
    "/api/diagnostics/open": {"diagnosticsView.js", "queue/rerunApi.js"},
    "/api/diagnostics/tdarr-matrix-audit": {"diagnostics/matrixConsole.js"},
    "/api/diagnostics/tdarr-matrix/evidence/open": {"diagnostics/matrixConsole.js"},
    "/api/diagnostics/tdarr-matrix/rerun": {"diagnostics/matrixConsole.js"},
    "/api/diagnostics/encoder-capabilities/refresh": {"launchView.preflight.js"},
    "/api/completed/reconcile-manifest-dry-run": {"completedView.repair.js"},
    "/api/completed/reconcile-manifest": {"completedView.repair.js"},
    "/api/completed/repair-sidecar-metadata-dry-run": {"completedView.repair.js"},
    "/api/completed/repair-sidecar-metadata": {"completedView.repair.js"},
    "/api/pending-publish/open": {"pendingPublishView.diagnostics.js"},
    "/api/pending-publish/recovery-plan": {"pendingPublishView.recovery.js"},
    "/api/pending-publish/repair-manifest-dry-run": {"pendingPublishView.repair.js"},
    "/api/pending-publish/repair-manifest": {"pendingPublishView.repair.js"},
    "/api/pending-publish/reconcile-orphan-payloads-dry-run": {"pendingPublishView.repair.js"},
    "/api/pending-publish/reconcile-orphan-payloads": {"pendingPublishView.repair.js"},
    "/api/queue/open": {"queue/openActions.js"},
    "/api/queue/scan": {"queue/scan.js"},
    "/api/queue/priority": {"queue/manualOrder.js", "queue/priority.js"},
    "/api/queue/strategy": {"queue/strategy.js"},
    "/api/queue/file-overrides": {"queue/fileOverrides.drawer.api.js"},
    "/api/queue/file-overrides/route-preview": {"queue/fileOverrides.routePreview.js"},
    "/api/settings/preset-library/validate": {"settings/presetLibrary.js"},
    "/api/settings/preset-library/compare": {"settings/presetLibrary.js"},
    "/api/settings/preset-library/import-preview": {"settings/presetLibrary.js"},
    "/api/settings/preset-library/save": {"settings/presetLibrary.js"},
    "/api/settings/preset-library/export": {"settings/presetLibrary.js"},
    "/api/settings/preset-library/apply-preview": {"settings/presetLibrary.js"},
    "/api/settings/preset-library/apply": {"settings/presetLibrary.js"},
    "/api/queue/file-overrides/series-preview": {"queue/fileOverrides.drawer.series.js"},
    "/api/queue/file-overrides/series-apply": {"queue/fileOverrides.drawer.series.js"},
    "/api/queue/file-overrides/series-clear-preview": {"queue/fileOverrides.drawer.series.js"},
    "/api/queue/file-overrides/series-clear-apply": {"queue/fileOverrides.drawer.series.js"},
    "/api/queue/file-overrides/remux-pilot-promote": {"queue/fileOverrides.drawer.series.js"},
    "/api/failures/clear": {"reports/failureCommands.js"},
    "/api/failures/archive-evidence": {"reports/failureCommands.js"},
    "/api/failures/open": {"reports/failureCommands.js"},
    "/api/failures/artifacts/cleanup": {"reports/failureCommands.js"},
    "/api/failures/lifecycle": {"reports/failureCommands.js"},
    "/api/rename/apply": {"renameView.js"},
    "/api/rename/browse": {"rename/paths.js"},
    "/api/rename/filter-cases": {"rename/selection.js"},
    "/api/rename/preview": {"rename/previewLifecycle.js"},
    "/api/rename/undo": {"renameView.js"},
    "/api/schedule/preview": {"schedule/editor.js"},
    "/api/schedule/save": {"schedule/editor.js"},
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
}
REPAIR_RECONCILE_ROUTE_TERMS = ("repair", "reconcile", "reconciliation")
ALLOWED_TAURI_EVENT_BRIDGE = "tauriLifecycleBridge.js"
RENAME_ASSET_NAMES = (
    "rename/cleaningFilters.js",
    "rename/cleaningWorkbench.js",
    "rename/selection.js",
    "rename/paths.js",
    "rename/preview.js",
    "rename/applyReadiness.js",
    "rename/editing.js",
    "rename/applyResult.js",
    "rename/commandEvidence.js",
    "rename/previewLifecycle.js",
    "rename/interactions.js",
    "rename/confirmSummary.js",
    "rename/dialogs.js",
    "renameView.js",
)


def _asset_sources() -> dict[str, str]:
    return {
        path.relative_to(ASSET_ROOT).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(ASSET_ROOT.rglob("*.js"))
    }


def _network_asset_source(sources: dict[str, str] | None = None) -> str:
    loaded_sources = sources if sources is not None else _asset_sources()
    return "\n".join(
        loaded_sources[name]
        for name in NETWORK_ASSET_NAMES
        if name in loaded_sources
    )


def _rename_asset_source(sources: dict[str, str] | None = None) -> str:
    loaded_sources = sources if sources is not None else _asset_sources()
    return "\n".join(loaded_sources[name] for name in RENAME_ASSET_NAMES if name in loaded_sources)


def _schedule_asset_source(sources: dict[str, str] | None = None) -> str:
    loaded_sources = sources if sources is not None else _asset_sources()
    return "\n".join(loaded_sources[name] for name in SCHEDULE_ASSET_NAMES if name in loaded_sources)


def _diagnostics_asset_source(sources: dict[str, str] | None = None) -> str:
    loaded_sources = sources if sources is not None else _asset_sources()
    return "\n".join(loaded_sources[name] for name in DIAGNOSTICS_ASSET_NAMES if name in loaded_sources)


def _maintenance_asset_source(sources: dict[str, str] | None = None) -> str:
    loaded_sources = sources if sources is not None else _asset_sources()
    return "\n".join(loaded_sources[name] for name in MAINTENANCE_ASSET_NAMES if name in loaded_sources)


def _is_network_contract_dynamic_dispatch(name: str, source: str, dynamic_call_count: int) -> bool:
    has_lifecycle_guards = (
        "network_lifecycle_contracts" in source
        and "confirm_start" in source
        and "confirm_stop" in source
    )
    has_setup_guards = (
        "networkCommandRouteByDataSchema" in source
        and "confirm_create" in source
        and "confirm_import" in source
    )
    return (
        name in NETWORK_DYNAMIC_DISPATCH_ASSETS
        and dynamic_call_count == 1
        and "apiPost(route, request)" in source
        and (has_lifecycle_guards or has_setup_guards)
    )


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
        for match in API_POST_DISPATCH_LITERAL_RE.finditer(source):
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
                dynamic_call_count = len(all_calls) - len(literal_matches)
                if _is_network_contract_dynamic_dispatch(name, source, dynamic_call_count):
                    continue
                unexpected.append(f"{name}: apiPost call must use a literal documented route")
                continue
            for match in literal_matches:
                route = match.group("route")
                if route not in contract_post_routes:
                    unexpected.append(f"{name}: {route} is not in LOCAL_API_ROUTE_CONTRACT")
            for match in API_POST_DISPATCH_LITERAL_RE.finditer(source):
                route = match.group("route")
                if route not in contract_post_routes:
                    unexpected.append(f"{name}: {route} is not in LOCAL_API_ROUTE_CONTRACT")

        self.assertEqual(unexpected, [])

    def test_api_post_command_ownership_stays_page_specific(self) -> None:
        self.assertEqual(_literal_api_post_owners(), EXPECTED_API_POST_OWNERS)

    def test_network_lifecycle_dispatch_uses_backend_contract_routes_and_confirmation_prompt(self) -> None:
        source = _network_asset_source()
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
        diagnostics_view = _diagnostics_asset_source()
        diagnostics_html = DIAGNOSTICS_PARTIAL.read_text(encoding="utf-8")

        self.assertNotIn("/api/pipeline/control", diagnostics_view)
        self.assertNotIn("diagnostics-force-reset", diagnostics_view)
        self.assertNotIn("diagnostics-force-reset", diagnostics_html)
        self.assertIn(
            "Diagnostics is read-only. If evidence shows stuck progress",
            diagnostics_html,
        )

    def test_tdarr_matrix_findings_render_in_diagnostics_table(self) -> None:
        diagnostics_view = _diagnostics_asset_source()
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
        app_js = "\n".join((
            _asset_sources()["app/dashboard.js"],
            _asset_sources()["app/refreshCoordinator.js"],
            _asset_sources()["app.js"],
        ))
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
        app_js = "\n".join((
            _asset_sources()["app/dashboard.js"],
            _asset_sources()["app/refreshCoordinator.js"],
            _asset_sources()["app.js"],
        ))
        progress_js = "\n".join((
            _asset_sources()["progress/barState.js"],
            _asset_sources()["progress/barPresentation.js"],
            _asset_sources()["progress/audit.js"],
            _asset_sources()["progress/details.js"],
            _asset_sources()["progress/diagnostics.js"],
            _asset_sources()["progress/activeWork.js"],
            _asset_sources()["progress/evidence.js"],
            _asset_sources()["progress/evidenceRows.js"],
            _asset_sources()["progress/liveRun.js"],
            _asset_sources()["progress/csvRerun.js"],
            _asset_sources()["progress/worker.js"],
            _asset_sources()["progress/ffmpegEta.js"],
            _asset_sources()["progress/timelineCore.js"],
            _asset_sources()["progress/timelineView.js"],
            _asset_sources()["progressView.js"],
        ))
        home_js = "\n".join((
            _asset_sources()["app/home/dailyDriver.js"],
            _asset_sources()["app/home/queueProjection.js"],
            _asset_sources()["app/home.js"],
        ))
        pending_js = "\n".join((
            _asset_sources()["pendingPublish/rendering.js"],
            _asset_sources()["pendingPublishView.js"],
        ))

        for html, prefix in [
            (home_html, "home"),
            (launch_html, "launch"),
            (pending_html, "pending"),
            (diagnostics_html, "diagnostics"),
        ]:
            self.assertIn(f'id="{prefix}-live-run-status"', html)
            self.assertIn(f'id="{prefix}-live-run-strip"', html)
            self.assertIn('class="live-run-strip"', html)

        self.assertIn('class="panel live-run-strip-panel" data-panel-type="status"', home_html)
        self.assertIn('id="queue-count-detail" class="metric-detail"', home_html)
        self.assertIn("function renderLiveRunStrip", progress_js)
        self.assertIn("function liveRunStripItems", progress_js)
        self.assertIn("function runTimelineItems", progress_js)
        self.assertIn("function renderProgressBars(bars = [], snapshot = null, context = {})", progress_js)
        self.assertIn("runTimelineItems,", progress_js)
        self.assertIn("function csvRerunTailEvidence", progress_js)
        self.assertIn("function csvRerunActivityEvidence", progress_js)
        self.assertIn("csvRerunWorkerLooksActive", progress_js)
        self.assertRegex(progress_js, r'liveRunItem\(\s*"Importing"')
        self.assertRegex(progress_js, r'liveRunItem\(\s*"Last imported"')
        self.assertRegex(progress_js, r'liveRunItem\(\s*"Processing"')
        self.assertIn("function refreshLiveRunTail", app_js)
        self.assertIn("function csvRerunActivityEvidence", app_js)
        self.assertIn("function renderCsvRerunHomeSummary", app_js)
        self.assertIn("renderCsvRerunHomeSummary(liveRunContext)", app_js)
        self.assertIn("renderHomePipelineState(\"csv_rerun_active\")", app_js)
        self.assertIn("renderHomeNextQueue({ ...liveRunContext, queue: lastQueue || {} })", app_js)
        self.assertIn("function homeCsvRerunQueueContext", home_js)
        self.assertIn("void refreshLiveRunTail(refreshOptions);", app_js)
        self.assertIn('/api/diagnostics/tail?target=last_stdout_log&max_bytes=65536', app_js)
        self.assertIn("progressBarForStableDisplay", progress_js)
        self.assertIn('track.setAttribute("aria-valuetext", progressBarStatusLabel(bar));', progress_js)
        self.assertIn("renderLiveRunStrip?.({", app_js)
        self.assertIn('id="pending-drain-progress-bars"', pending_html)
        self.assertIn("function renderPendingDrainProgress", pending_js)
        self.assertIn('"pending_drain"', pending_js)
        self.assertNotIn('apiPost("/api/progress', progress_js)

    def test_ui_preferences_sync_stays_allowlisted_and_runs_before_layout_init(self) -> None:
        sources = _asset_sources()
        app_js = sources["app.js"]
        preferences_js = sources["app/uiPreferences.js"]
        startup_js = sources["app/lifecycleOrchestration.js"]

        self.assertIn('apiGet("/api/ui-preferences", { timeoutMs: 5000 })', preferences_js)
        self.assertIn("const keyPattern = /^mediapipeline[-.]", preferences_js)
        self.assertIn("let syncPending = false;", preferences_js)
        self.assertIn("let localDirty = false;", preferences_js)
        self.assertIn("let awaitingRemoteEchoSerialized = \"\";", preferences_js)
        self.assertIn('bootstrap.shellSurface || bootstrap.shell_surface || "webview"', preferences_js)
        self.assertIn('if (surface() !== "tauri" && Object.keys(local).length)', preferences_js)
        self.assertIn("storage.removeItem(key)", preferences_js)
        self.assertIn("syncPending = true;", preferences_js)
        self.assertIn("localDirty = true;", preferences_js)
        self.assertIn("function hasPendingWrite()", preferences_js)
        self.assertIn("hasPendingWrite() && remoteSerialized !== localSerialized", preferences_js)
        self.assertIn("awaitingRemoteEchoSerialized === localSerialized", preferences_js)
        self.assertIn("await persist({ force: true });", preferences_js)
        self.assertLess(
            preferences_js.index("function hasPendingWrite()"),
            preferences_js.index("async function restore(options"),
        )
        self.assertIn("await restoreSharedUiPreferences();", startup_js)
        self.assertIn("installSharedUiPreferenceStorageSync();", startup_js)
        self.assertIn("startSharedUiPreferenceRemoteRefresh();", startup_js)
        self.assertIn("function applySharedUiPreferenceRuntimeState()", app_js)
        self.assertIn("function applyStoredLayoutPreferences()", app_js)
        install_index = startup_js.index("installSharedUiPreferenceStorageSync();")
        self.assertLess(startup_js.index("await restoreSharedUiPreferences();"), install_index)
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
                self.assertLess(install_index, startup_js.index(startup_call))
        self.assertIn("const result = await postPreferences(nextPayload", preferences_js)
        self.assertIn('postPreferences: (payload, options) => apiPost("/api/ui-preferences", payload, options)', app_js)
        self.assertIn("if (result && result.ok === false)", preferences_js)

    def test_shell_open_routes_submit_backend_selector_keys_not_raw_paths(self) -> None:
        specs = {
            "/api/diagnostics/open": ("diagnosticsView.js", {"target"}),
            "/api/diagnostics/tdarr-matrix/evidence/open": ("diagnostics/matrixConsole.js", {"run_id", "finding_key", "target"}),
            "/api/diagnostics/tdarr-matrix/rerun": ("diagnostics/matrixConsole.js", {"source_run_id", "selection", "finding_keys"}),
            "/api/queue/open": ("queue/openActions.js", {"row_key", "row_scope", "target"}),
            "/api/completed/open": ("completed/openActions.js", {"row_key", "target"}),
            "/api/pending-publish/open": ("pendingPublishView.diagnostics.js", {"row_key", "target"}),
            "/api/maintenance/dependency-atlas/open-folder": ("maintenance/releaseCommands.js", set()),
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
        reports_failure_commands_js = _asset_sources()["reports/failureCommands.js"]
        self.assertIn('apiPost("/api/failures/clear", payload)', reports_failure_commands_js)
        self.assertIn('const apiScope = clearAll ? "all_markers" : normalizedScope === "selected_group" ? "selected" : normalizedScope;', reports_failure_commands_js)
        self.assertIn("scope: request.scope", reports_failure_commands_js)
        self.assertIn("if (!request.all_markers) payload.marker_paths = request.marker_paths;", reports_failure_commands_js)
        self.assertIn("confirm_clear: !dryRun", reports_failure_commands_js)
        self.assertIn('apiPost("/api/failures/archive-evidence", request)', reports_failure_commands_js)
        self.assertIn("confirm_archive: !dryRun", reports_failure_commands_js)
        settings_js = _asset_sources()["settingsView.js"]
        self.assertIn('"/api/settings/save-patch"', settings_js)
        self.assertIn("review_confirmation: reviewConfirmation", settings_js)
        self.assertIn("confirm_save: true", settings_js)
        settings_wizard = _asset_sources()["settingsWizard.js"]
        self.assertIn('apiPostLocal("/api/settings/wizard/save", {', settings_wizard)
        self.assertIn("confirm_save: true", settings_wizard)
        self.assertIn("review_confirmation: state.lastPreview?.data?.review_confirmation || null", settings_wizard)
        self.assertIn('apiPost("/api/schedule/save", { ...request, confirm_save: true })', _schedule_asset_source())
        maintenance_js = _maintenance_asset_source()
        self.assertIn("confirm_create: true", maintenance_js)
        self.assertIn("include_tauri_preview_binary", maintenance_js)
        completed_js = _asset_sources()["completed/promotionCommands.js"]
        self.assertIn("const request = { confirm_promote: true };", completed_js)
        self.assertIn("if (selectedRowKeys.length) request.row_keys = selectedRowKeys;", completed_js)
        self.assertIn('apiPost("/api/final-library-promotion/promote-queue", request)', completed_js)
        queue_rerun_js = _asset_sources()["queueView.rerun.js"]
        queue_rerun_api_js = _asset_sources()["queue/rerunApi.js"]
        queue_rerun_request_js = _asset_sources()["queue/rerunRequest.js"]
        launch_rerun_presentation_js = _asset_sources()["launch/rerunPresentation.js"]
        self.assertIn('requireApiPost(RERUN_CONTROL_ROUTE)("/api/rerun/control", { action: "stop_after_current", confirm_stop: true })', queue_rerun_api_js)
        self.assertIn('requireApiPost(RERUN_CONTROL_ROUTE)("/api/rerun/control", { action: "pause", confirm_pause: true })', queue_rerun_api_js)
        self.assertIn('requireApiPost(RERUN_NETWORK_START_DRY_RUN_ROUTE)("/api/rerun/network/start-dry-run", request)', queue_rerun_api_js)
        self.assertIn('requireApiPost(RERUN_NETWORK_START_ROUTE)("/api/rerun/network/start", request)', queue_rerun_api_js)
        self.assertIn("const request = { manifest_key: key, confirm_continue: true };", launch_rerun_presentation_js)
        self.assertIn("confirm_start: true", queue_rerun_request_js)
        self.assertIn("dry_run_fingerprint: fingerprint", queue_rerun_request_js)
        self.assertIn('requireApiPost(RERUN_CONTINUE_ROUTE)("/api/rerun/continue", request)', queue_rerun_api_js)
        self.assertIn('requireApiPost(RERUN_PROMOTE_DRY_RUN_ROUTE)("/api/rerun/promote-dry-run", { row_key: rowKey })', queue_rerun_api_js)
        self.assertIn("const request = { row_key: key, dry_run_fingerprint: fingerprint, confirm_promote: true };", queue_rerun_js)
        self.assertIn('requireApiPost(RERUN_PROMOTE_ROUTE)("/api/rerun/promote", request)', queue_rerun_api_js)

    def test_queue_loaded_priority_copy_does_not_imply_launch_scope(self) -> None:
        queue_html = QUEUE_PARTIAL.read_text(encoding="utf-8")
        queue_view = "\n".join((
            _asset_sources()["queue/statusPanels.js"],
            _asset_sources()["queue/tableView.js"],
            _asset_sources()["queue/priority.js"],
            _asset_sources()["queue/manualOrder.js"],
            _asset_sources()["queue/strategy.js"],
            _asset_sources()["queue/controls.js"],
            _asset_sources()["queue/excluded.js"],
            _asset_sources()["queue/scan.js"],
            _asset_sources()["queueView.js"],
        ))

        for snippet in [
            "All Loaded Movies",
            "All Loaded TV",
            "loaded queue rows regardless of display filters or render cap",
            "They do not define Launch scope",
            "Save Loaded Backend Order",
            "Save Loaded Backend Order writes the staged positions",
            "Display filters and render caps do not define Launch scope",
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
        rename_view = _rename_asset_source()
        settings_view = _asset_sources()["settingsView.js"]
        settings_html = SETTINGS_PARTIAL.read_text(encoding="utf-8")

        for snippet in [
            "shows the change review dialog",
            "Save gathers these rename-filter values",
            "Browser storage is local draft recovery only; filesystem changes still require backend rename apply confirmation",
            "Save Settings",
            "Rename Filter Case Workbench",
            "stage new filter terms into the Settings draft",
            "Retest With Staged Filters",
            "Save New Filters",
            "settings-rename-workbench-save-case-button",
            "settings-rename-workbench-stage-suggestions-button",
            "settings-rename-workbench-save-filters-button",
            "Guided setup prepares the same PSD1-backed settings used by the manual editor.",
            "Save goes through backend validation",
        ]:
            with self.subTest(asset="page-settings.html", snippet=snippet):
                self.assertIn(snippet, settings_html)
        self.assertNotIn("Guided setup writes PSD1", settings_html)
        self.assertNotIn("validates locally", settings_html)
        for snippet in [
            "function stageRenameCleaningFilterPatch(changes)",
            "Rename filter changes prepared for Save Settings; no backend save route was called.",
            "Next step: press Save Settings.",
            "Browser storage is local draft recovery only",
        ]:
            with self.subTest(asset="renameView.js", snippet=snippet):
                self.assertIn(snippet, rename_view)
        self.assertNotIn('/api/settings/preview-patch', rename_view)
        self.assertNotIn('/api/settings/save-patch', rename_view)
        self.assertIn("function settingsRenameLogCasePayload()", settings_view)
        self.assertIn("renameView.submitRenameBadCasePayload(payload)", settings_view)
        self.assertNotIn('apiPost("/api/rename/filter-cases"', settings_view)

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

    def test_shared_path_picker_browse_is_allowlisted_staging_only(self) -> None:
        source = _asset_sources()["pathPicker.js"]

        self.assertIn('apiPost("/api/path-picker/browse"', source)
        self.assertIn("target_key: targetKey", source)
        self.assertIn("selection_mode", source)
        self.assertIn("initial_path", source)
        self.assertIn("file_filter", source)
        self.assertIn("path-picker:staged", source)
        self.assertNotIn("confirm_save", source)
        self.assertNotIn("confirm_apply", source)
        self.assertNotIn("confirm_promote", source)
        browse_contract = next(route for route in LOCAL_API_ROUTE_CONTRACT if route["path"] == "/api/path-picker/browse")
        self.assertEqual(browse_contract["effect"], "shell-dialog")
        self.assertEqual(browse_contract["allowed_selection_modes"], ["files", "folder", "folder_files"])
        self.assertEqual(
            browse_contract["request_keys"],
            ["target_key", "selection_mode", "initial_path", "file_filter"],
        )
        self.assertEqual(browse_contract["data_schema"], "desktop_path_picker_browse.v1")
        self.assertIn("staged-only", browse_contract["purpose"])
        self.assertIn("allowlisted", browse_contract["purpose"])
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
            "/api/path-picker/browse",
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

    def test_repair_reconcile_backend_routes_exist_and_webview_exposes_bounded_repair_controls(self) -> None:
        payload = local_api_contract_payload(app_version="v5-test", host="127.0.0.1")
        summary = payload["repair_reconcile_summary"]

        self.assertEqual(summary["status"], "backend_dry_run_and_confirmed_apply_routes_available_startup_dry_run_only")
        self.assertTrue(summary["mutation_enabled"])
        self.assertTrue(summary["frontend_allowed"])
        self.assertIn("Confirmed apply routes are backend-owned", summary["safe_next_step"])
        self.assertIn("startup reconciliation remains dry-run only", summary["safe_next_step"])
        allowed_apply_routes = {
            "/api/completed/reconcile-manifest": "completed-manifest-write",
            "/api/completed/repair-sidecar-metadata": "completed-sidecar-json-write",
            "/api/pending-publish/repair-manifest": "pending-manifest-write",
            "/api/pending-publish/reconcile-orphan-payloads": "pending-orphan-manifest-write",
        }
        for contract in payload["repair_reconcile_contracts"]:
            with self.subTest(contract=contract["key"]):
                self.assertIn("dry_run_route", contract)
                self.assertEqual(contract["dry_run_contract"]["effect"], "none")
                self.assertIn("dry_run_only", contract["dry_run_contract"]["required_result_fields"])
                self.assertIn("would_not_touch", contract["dry_run_contract"]["required_result_fields"])
                self.assertTrue(contract["rollback_contract"]["required_for_mutation_route"])
                self.assertTrue(contract["rollback_contract"]["journal_required"])
                self.assertEqual(contract["source_file_policy"]["source_media_mutation"], "forbidden")
                self.assertTrue(any("API_ROUTE_INVENTORY.md" in gate for gate in contract["route_exposure_gates"]))
                if contract["key"] == "startup_state_reconcile":
                    self.assertEqual(contract["current_status"], "backend_dry_run_route_available")
                    self.assertNotIn("apply_route", contract)
                    self.assertFalse(contract["mutation_enabled"])
                    self.assertFalse(contract["frontend_allowed"])
                else:
                    self.assertEqual(contract["current_status"], "backend_dry_run_and_confirmed_apply_routes_available")
                    self.assertIn("apply_route", contract)
                    self.assertTrue(contract["mutation_enabled"])
                    self.assertTrue(contract["frontend_allowed"])
                    self.assertEqual(contract["apply_contract"]["effect"], allowed_apply_routes[contract["apply_route"]])

        allowed_dry_run_routes = {
            "/api/completed/reconcile-manifest-dry-run",
            "/api/completed/repair-sidecar-metadata-dry-run",
            "/api/pending-publish/repair-manifest-dry-run",
            "/api/pending-publish/reconcile-orphan-payloads-dry-run",
            "/api/startup/reconcile-dry-run",
        }
        callable_routes = [
            route
            for route in LOCAL_API_ROUTE_CONTRACT
            if str(route.get("method", "")).upper() == "POST"
            and any(term in str(route.get("path", "")).lower() for term in REPAIR_RECONCILE_ROUTE_TERMS)
        ]
        self.assertEqual({route["path"] for route in callable_routes}, allowed_dry_run_routes | set(allowed_apply_routes))
        for route in callable_routes:
            with self.subTest(route=route["path"]):
                if route["path"] in allowed_dry_run_routes:
                    self.assertEqual(
                        route["data_schema"],
                        (
                            "desktop_startup_reconciliation_dry_run.v1"
                            if route["path"] == "/api/startup/reconcile-dry-run"
                            else "desktop_repair_reconcile_dry_run.v1"
                        ),
                    )
                    self.assertFalse(route["mutation_enabled"])
                    self.assertFalse(route["frontend_exposed"])
                    self.assertEqual(route["effect"], "none")
                    continue
                self.assertEqual(route["data_schema"], "desktop_repair_reconcile_apply.v1")
                self.assertEqual(route["effect"], allowed_apply_routes[route["path"]])
                self.assertTrue(route["mutation_enabled"])
                self.assertTrue(route["frontend_exposed"])

        read_only_publish_reconciliation = [
            route
            for route in LOCAL_API_ROUTE_CONTRACT
            if route.get("path") == "/api/publish-reconciliation"
        ]
        self.assertTrue(read_only_publish_reconciliation)
        for route in read_only_publish_reconciliation:
            with self.subTest(route=route["path"]):
                self.assertEqual(route["effect"], "none")

        post_repair_routes = {
            route: owners
            for route, owners in _literal_api_post_owners().items()
            if any(term in route.lower() for term in REPAIR_RECONCILE_ROUTE_TERMS)
        }
        self.assertEqual(
            post_repair_routes,
            {
                "/api/completed/reconcile-manifest-dry-run": {"completedView.repair.js"},
                "/api/completed/reconcile-manifest": {"completedView.repair.js"},
                "/api/completed/repair-sidecar-metadata-dry-run": {"completedView.repair.js"},
                "/api/completed/repair-sidecar-metadata": {"completedView.repair.js"},
                "/api/pending-publish/repair-manifest-dry-run": {"pendingPublishView.repair.js"},
                "/api/pending-publish/repair-manifest": {"pendingPublishView.repair.js"},
                "/api/pending-publish/reconcile-orphan-payloads-dry-run": {"pendingPublishView.repair.js"},
                "/api/pending-publish/reconcile-orphan-payloads": {"pendingPublishView.repair.js"},
            },
        )

        pending_repair_view = _asset_sources()["pendingPublishView.repair.js"]
        for snippet in [
            "/api/pending-publish/repair-manifest-dry-run",
            "/api/pending-publish/repair-manifest",
            "/api/pending-publish/reconcile-orphan-payloads-dry-run",
            "/api/pending-publish/reconcile-orphan-payloads",
            "pending_publish.reconcile_orphan_payloads",
            "pendingRepairOrphanApplyRequest",
            "scope: \"selected\"",
            "row_key: rowKey",
            "limit: 1",
            "dry_run_fingerprint: fingerprint",
            "confirm_apply: true",
            "data.safe_to_apply === true",
            "window.confirm",
            "Mutation guardrail: this control sends only backend route intent.",
        ]:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, pending_repair_view)
        for forbidden in [
            "manifest_path:",
            "local_file:",
            "server_out:",
            "source_path:",
            "payload_path:",
            "sidecar_json:",
            "patch:",
            "/api/completed/reconcile-manifest",
            "/api/completed/repair-sidecar-metadata",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, pending_repair_view)

        completed_repair_view = _asset_sources()["completedView.repair.js"]
        for snippet in [
            "/api/completed/reconcile-manifest-dry-run",
            "/api/completed/reconcile-manifest",
            "/api/completed/repair-sidecar-metadata-dry-run",
            "/api/completed/repair-sidecar-metadata",
            "scope: \"selected\"",
            "row_key: rowKey",
            "limit: 1",
            "dry_run_fingerprint: fingerprint",
            "confirm_apply: true",
            "data.safe_to_apply === true",
            "window.confirm",
            "Mutation guardrail: Completed repair controls send only backend route intent.",
        ]:
            with self.subTest(snippet=snippet):
                self.assertIn(snippet, completed_repair_view)
        for forbidden in [
            "manifest_path:",
            "local_file:",
            "server_out:",
            "source_path:",
            "output_path:",
            "payload_path:",
            "sidecar_json:",
            "patch:",
            "/api/pending-publish/reconcile-orphan-payloads",
            "/api/pending-publish/repair-manifest",
        ]:
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, completed_repair_view)

        contract_view = _asset_sources()["contractView.js"]
        for snippet in [
            "Repair/reconcile boundary",
            "mutation enabled",
            "frontend allowed",
            "backend dry-runs exist",
            "mutation controls remain forbidden",
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
            "backend Save remains",
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
        app = "\n".join((sources["app/lifecycleOrchestration.js"], sources["app.js"]))

        for snippet in [
            "mediapipeline://backend-lifecycle",
            "mediapipeline:backend-lifecycle",
            "tauri://drag-drop",
            "mediapipeline:file-drop",
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
            "disable_drag_drop_handler",
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
