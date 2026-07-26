from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root

sys.path.insert(0, str(find_repo_root(Path(__file__)) / "src"))

from mediapipeline.desktop.api.contract import LOCAL_API_ROUTE_CONTRACT
from mediapipeline.desktop.api.static_files import render_index
from tests.css_import_resolver import resolve_css_imports

REPO_ROOT = find_repo_root(Path(__file__))
STATIC_ROOT = REPO_ROOT / "apps" / "desktop" / "webview" / "static"
INDEX_HTML = STATIC_ROOT / "index.html"
NETWORK_JS = STATIC_ROOT / "assets" / "networkView.js"
NETWORK_BUILDER_JS = STATIC_ROOT / "assets" / "settingsView.builders.network.js"
STYLES_PAGES_CSS = STATIC_ROOT / "assets" / "styles.pages.css"
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


def _existing_network_asset_sources() -> dict[str, str]:
    sources: dict[str, str] = {}
    for name in NETWORK_ASSET_NAMES:
        path = STATIC_ROOT / "assets" / name
        if path.exists():
            sources[name] = path.read_text(encoding="utf-8")
    if "networkView.js" not in sources:
        raise AssertionError("networkView.js must remain the public Network facade")
    return sources


def _network_asset_source() -> str:
    return "\n".join(_existing_network_asset_sources().values())


def _network_page_html() -> str:
    response = render_index(
        STATIC_ROOT,
        {"token": "network-test-token", "appVersion": "v6-test", "shellSurface": "webview"},
    )
    if response.status != 200:
        raise AssertionError(f"index render failed with status {response.status}: {response.body!r}")
    html = response.body.decode("utf-8")
    start = html.index('<section class="page" data-page-panel="network">')
    end = html.index('<section class="page" data-page-panel="maintenance">', start)
    return html[start:end]


def _read_pages_css() -> str:
    return resolve_css_imports(STYLES_PAGES_CSS, STATIC_ROOT / "assets")


def _button_labels_and_attrs(html: str) -> list[tuple[str, str]]:
    rows: list[tuple[str, str]] = []
    for match in re.finditer(r"<button\b(?P<attrs>[^>]*)>(?P<label>.*?)</button>", html, flags=re.DOTALL | re.IGNORECASE):
        label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group("label"))).strip()
        rows.append((label, match.group("attrs")))
    return rows


def _h2_texts(html: str) -> list[str]:
    rows: list[str] = []
    for match in re.finditer(r"<h2\b[^>]*>(?P<label>.*?)</h2>", html, flags=re.DOTALL | re.IGNORECASE):
        label = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", match.group("label"))).strip()
        rows.append(label)
    return rows


class WebViewNetworkReadOnlyBoundaryTests(unittest.TestCase):
    def test_workers_page_uses_evidence_first_panel_order(self) -> None:
        headings = _h2_texts(_network_page_html())

        self.assertEqual(
            headings,
            [
                "Network Command Board",
                "Worker Board",
                "Network CSV Rerun Status",
                "Coordinator At A Glance",
                "Worker At A Glance",
                "Join Worker to Cluster",
                "Saved Distributed Mode Settings Medium Impact",
                "Mode Summary",
                "Readiness + Lifecycle Boundary",
                "Network Config",
                "Open History",
                "Lifecycle Handoff",
                "Evidence Checklist",
                "State Files",
                "API Contract",
                "Unavailable Actions",
            ],
        )

    def test_network_settings_guidance_tiles_stay_hidden(self) -> None:
        network_html = _network_page_html()

        self.assertIn(
            'id="settings-network-guidance" class="prose-block" hidden aria-hidden="true"',
            network_html,
        )
        self.assertIn(
            'class="network-settings-patch-summary" hidden aria-hidden="true"',
            network_html,
        )
        self.assertIn('id="network-settings-control-status"', network_html)
        self.assertIn('id="network-settings-patch-handoff"', network_html)

    def test_workers_page_distinguishes_saved_and_persisted_state_labels(self) -> None:
        network_html = _network_page_html()
        network_view_js = "\n".join((
            (NETWORK_JS.parent / "network" / "rerunEvidence.js").read_text(encoding="utf-8"),
            NETWORK_JS.read_text(encoding="utf-8"),
        ))

        for expected in (
            "Network Command Board",
            "Role",
            "Runtime",
            "Coordinator",
            "Drift",
            "Workers",
            "Alerts",
            'id="network-attention-stack"',
            'id="network-topology-strip"',
            'id="network-diagnostic-rail"',
            'id="network-action-readiness-gates"',
            "Worker Board",
            "Network CSV Rerun",
            'id="network-rerun-status"',
            'id="network-rerun-rows"',
            'id="network-rerun-detail"',
            'id="network-worker-view-presets"',
            "Selected Worker Inspector",
            "Coordinator At A Glance",
            "Active Claimed Work",
            "Queue On Deck",
            "Worker At A Glance",
            "Local Worker Claim",
            "Remote Queue Visibility",
            "Join Worker to Cluster",
            "Settings",
            "Advanced Evidence",
            "Unavailable Actions",
            "Mode Model",
            "Lifecycle Boundary",
            "Workers Route Summary",
            "Last Reported Progress",
            "Saved Distributed Mode Settings",
            "Coordinator policy authority",
            "Worker-local execution ownership",
            'id="settings-network-worker-encoder-map"',
            'id="settings-network-honor-coordinator-policy"',
            "Open Coordinator Setup",
            "Open Worker Setup",
            "Designation",
            "Staged Patch: none",
            "If backend Python files were updated while the app/API was already running",
            'id="settings-network-worker-url-error"',
            'id="network-role-setup-worker-url-error"',
        ):
            self.assertIn(expected, network_html)
        for expected in (
            "function renderNetworkRerunRows",
            "Network CSV rerun read model: backend-owned /api/rerun/results.",
            "WebView does not author claims, row status, destination policy, Pending Publish paths, or final output paths.",
            "renderNetworkRerunRows(payload.rerunResults || {})",
        ):
            self.assertIn(expected, network_view_js)

    def test_workers_api_contract_detail_is_advanced_only(self) -> None:
        network_html = _network_page_html()
        first_advanced = network_html.index('id="network-advanced-evidence-drawer"')

        self.assertGreater(network_html.index("Workers Route Summary"), first_advanced)
        self.assertGreater(network_html.index("<h2>API Contract</h2>"), first_advanced)
        self.assertRegex(
            network_html,
            r'<details class="network-command-drawer" id="network-advanced-evidence-drawer" data-advanced>[\s\S]*'
            r'<h2>API Contract</h2>',
        )

    def test_workers_page_buttons_are_diagnostics_lifecycle_or_settings_only(self) -> None:
        buttons = _button_labels_and_attrs(_network_page_html())
        labels = [label for label, _attrs in buttons]

        for expected in (
            "Configure Distributed Mode",
            "Open Logs",
            "Check &amp; Start Coordinator",
            "Request Coordinator Stop",
            "Open Cluster Log",
            "Configure",
            "Test Connection",
            "Check &amp; Start Worker",
            "Request Worker Stop",
            "Open Run Logs",
            "Open Cluster Log",
            "Open Active Jobs",
            "Open Config",
            "Open State Folder",
            "Create Join Blob",
            "Copy Blob",
            "Join Cluster",
            "Discover Coordinators",
            "Drain",
            "Disable New Work",
            "Pause",
            "Abort Current",
            "Reclaim Job",
            "Quarantine Worker",
            "Open Coordinator Setup",
            "Open Worker Setup",
            "Stage Distributed Settings",
            "Reset From Current",
            "Preview Settings Patch",
            "Save Distributed Settings",
            "Stage Settings",
            "Save Settings",
            "Close",
            "Cancel",
            "Confirm command",
            "All",
            "Active or needs attention",
            "Active Work",
            "Idle",
            "Stale/Failed",
            "Path/Auth",
        ):
            self.assertIn(expected, labels)
        diagnostics_buttons = [(label, attrs) for label, attrs in buttons if "data-open-diagnostics=" in attrs]
        self.assertEqual(len(diagnostics_buttons), 8)
        for _label, attrs in diagnostics_buttons:
            self.assertIn("data-open-diagnostics=", attrs)
            self.assertNotRegex(attrs, r"(?:^|\s)id\s*=")
        tab_buttons = [(label, attrs) for label, attrs in buttons if "data-network-tab=" in attrs]
        self.assertEqual(tab_buttons, [])
        lifecycle_buttons = [
            (label, attrs)
            for label, attrs in buttons
            if "data-network-lifecycle-role=" in attrs
        ]
        self.assertEqual(len(lifecycle_buttons), 4)
        for label, attrs in lifecycle_buttons:
            self.assertIn("data-network-lifecycle-action=", attrs, label)
            self.assertIn('data-network-lifecycle-guided="true"', attrs, label)
            self.assertNotIn("data-open-diagnostics=", attrs)
        future_buttons = [
            (label, attrs)
            for label, attrs in buttons
            if "data-network-future-control=" in attrs
        ]
        self.assertEqual(len(future_buttons), 6)
        for label, attrs in future_buttons:
            self.assertIn("disabled", attrs, label)
        allowed_setting_ids = {
            'id="network-role-coordinator-setup-button"',
            'id="network-role-worker-setup-button"',
            'id="settings-network-apply-button"',
            'id="settings-network-reset-button"',
            'id="settings-network-path-map-add-row"',
            'id="network-settings-preview-button"',
            'id="network-settings-save-button"',
            'id="network-role-setup-stage-button"',
            'id="network-role-setup-preview-button"',
            'id="network-role-setup-save-button"',
            'id="network-role-setup-close-button"',
            'id="network-role-setup-path-map-add-row"',
            'id="network-lifecycle-confirm-cancel"',
            'id="network-lifecycle-confirm-submit"',
            'id="network-coordinator-join-create"',
            'id="network-coordinator-join-copy"',
            'id="network-worker-join-import"',
            'id="network-worker-discover"',
        }
        for _label, attrs in buttons:
            if (
                "data-open-diagnostics=" in attrs
                or "data-network-open-drawer=" in attrs
                or "data-network-lifecycle-role=" in attrs
                or "data-network-future-control=" in attrs
                or "data-network-test-connection" in attrs
                or "data-network-worker-view" in attrs
                or 'id="network-open-queue-rerun-button"' in attrs
            ):
                continue
            self.assertTrue(any(item in attrs for item in allowed_setting_ids), attrs)

    def test_workers_page_setup_dialogs_are_settings_only(self) -> None:
        network_html = _network_page_html()

        for expected in (
            'id="network-role-setup-dialog"',
            'id="network-role-setup-coordinator-fields"',
            'id="network-role-setup-worker-fields"',
            'data-role-setup-source="settings-network-coordinator-port"',
            'data-role-setup-source="settings-network-worker-url"',
            'data-role-setup-source="settings-network-worker-encoder-map"',
            'data-role-setup-source="settings-network-honor-coordinator-policy"',
            'id="network-role-setup-worker-encoder-map"',
            'id="network-role-setup-honor-coordinator-policy"',
            'id="settings-network-path-map-rows"',
            'id="network-role-setup-path-map-rows"',
            'id="settings-network-path-map-test-result"',
            'id="network-role-setup-path-map-test-result"',
            "Distributed setup stages saved config only.",
            "Secrets remain backend-owned and are not displayed here.",
        ):
            self.assertIn(expected, network_html)
        self.assertNotIn("CoordinatorAuthToken", network_html)
        self.assertNotIn("WorkerAuthToken", network_html)

    def test_workers_page_setup_dialog_values_have_tips(self) -> None:
        source = NETWORK_BUILDER_JS.read_text(encoding="utf-8")

        for expected in (
            "What it means: this computer's distributed processing designation.",
            "Suggested: 7830 unless another local service already uses it.",
            "Suggested: 0.0.0.0 for LAN workers; 127.0.0.1 for local-only tests.",
            "Suggested: http://<coordinator-ip>:7830",
            "Do not use 0.0.0.0 or :: because those are listen addresses",
            "Suggested: the Windows computer name or a short role name such as BEAST-PC.",
            "Suggested: 10 to 15 seconds",
            "Suggested: {} when paths match",
            "worker-owned hardware map from coordinator codec families",
            "leave disabled until real-media validation",
            "Suggested: {} unless a specific worker needs tuning",
            "aria-describedby",
            "visually-hidden",
            "function workerCoordinatorUrlIssue",
            "function collectPathMapRowsStrict",
            "function testPathMapRow",
            "await runner({ render: false })",
            "Local staged rewrite result:",
            "Backend saved-config preflight",
            "Use the coordinator machine name or LAN IP",
            "aria-invalid",
        ):
            self.assertIn(expected, source)
        self.assertNotIn("accessible yes", source)
        self.assertNotIn("accessible no", source)

    def test_workers_page_setup_dialog_actions_are_mobile_safe(self) -> None:
        css = _read_pages_css()

        self.assertRegex(css, r"\.network-role-setup-actions\s*\{[^}]*position:\s*sticky", re.DOTALL)
        self.assertRegex(css, r"\.network-role-setup-actions\s*\{[^}]*bottom:\s*0", re.DOTALL)
        self.assertIn("@media (max-width: 600px)", css)
        self.assertIn("grid-template-columns: repeat(2, minmax(0, 1fr));", css)
        self.assertIn(".network-overview-grid", css)
        self.assertIn(".network-action-readiness-gates", css)
        self.assertIn(".network-worker-view-presets", css)
        self.assertIn("width: calc(100vw - 16px);", css)

    def test_workers_status_banner_lines_are_overflow_contained(self) -> None:
        css = _read_pages_css()
        network_html = _network_page_html()

        self.assertIn('id="network-status-banner-lines" class="network-status-banner-lines"', network_html)
        shared_match = re.search(
            r"\.network-status-banner span,\s*\.network-status-banner-lines\s*\{(?P<body>[^}]*)\}",
            css,
            re.S,
        )
        self.assertIsNotNone(shared_match)
        self.assertIn("min-width: 0;", shared_match.group("body"))
        self.assertIn("overflow-wrap: anywhere;", shared_match.group("body"))

        block_match = re.search(
            r"\.network-status-banner-lines\s*\{(?P<body>[^}]*)\}",
            css[shared_match.end() :],
            re.S,
        )
        self.assertIsNotNone(block_match)
        block_body = block_match.group("body")
        self.assertIn("max-height: 168px;", block_body)
        self.assertIn("overflow: auto;", block_body)
        self.assertIn("white-space: pre-wrap;", block_body)

    def test_workers_page_keeps_future_network_operations_disabled(self) -> None:
        network_html = _network_page_html()

        for future_control in ("drain", "disable-new-work", "pause", "abort-current", "reclaim-job", "quarantine-worker"):
            self.assertRegex(
                network_html,
                rf'data-network-future-control="{future_control}" disabled',
            )
        for forbidden in ("promote", "demote", "release", "retry", "delete", "publish", "rename"):
            self.assertNotIn(f'data-network-future-control="{forbidden}"', network_html)

    def test_network_asset_set_is_ready_for_child_split(self) -> None:
        sources = _existing_network_asset_sources()

        self.assertIn("networkView.js", sources)
        self.assertIn("window.mediaPipelineNetworkView", sources["networkView.js"])
        self.assertTrue(all(name.startswith("network/") for name in NETWORK_CHILD_ASSET_NAMES))

    def test_network_view_js_uses_only_backend_network_lifecycle_routes(self) -> None:
        source = _network_asset_source()

        self.assertNotRegex(source, r"\bfetch\s*\(")
        self.assertIn("function postNetworkLifecycleRoute", source)
        self.assertIn("function networkLifecycleRouteRow", source)
        self.assertIn("function networkLifecycleRoutePath", source)
        self.assertIn("route?.network_lifecycle", source)
        self.assertIn("apiPost(route, request)", source)
        self.assertIn("function confirmNetworkLifecycleCommand", source)
        self.assertIn("function confirmNetworkSetupCommand", source)
        self.assertIn("network-lifecycle-confirm-dialog", source)
        self.assertIn("networkLifecycleDryRunEvidence", source)
        self.assertIn("function networkLifecycleDryRunAllowsConfirmed", source)
        self.assertIn("function networkLifecycleFingerprint", source)
        self.assertIn("function networkSetupMutationRouteSummary", source)
        self.assertIn("function networkWorkerTestConnectionRoute", source)
        self.assertIn("function networkTestConnectionResultLines", source)
        self.assertIn("function runNetworkWorkerTestConnection", source)
        self.assertIn("desktop_network_worker_test_connection.v1", source)
        self.assertIn("function networkCommandRouteByDataSchema", source)
        self.assertIn("function networkCoordinatorJoinBlobRoute", source)
        self.assertIn("function networkWorkerJoinClusterRoute", source)
        self.assertIn("function networkWorkerDiscoverCoordinatorsRoute", source)
        self.assertIn("function createNetworkJoinBlob", source)
        self.assertIn("function copyNetworkJoinBlob", source)
        self.assertIn("function importNetworkJoinBlob", source)
        self.assertIn("function discoverNetworkCoordinators", source)
        self.assertIn("function networkCoordinatorDiscoveryResultLines", source)
        self.assertIn("function renderNetworkCoordinatorDiscoveryList", source)
        self.assertIn("function stageDiscoveredCoordinatorUrl", source)
        self.assertNotIn("Stopping may abort active worker work", source)
        self.assertIn("stop polling/new claims", source)
        self.assertIn("active work is preserved for done reporting", source)
        self.assertIn("Matching dry-run required", source)
        self.assertIn("Create Join Blob was cancelled before the backend confirmation field was sent.", source)
        self.assertIn("Join Cluster was cancelled before the backend confirmation field was sent.", source)
        self.assertIn("desktop_network_join_blob_result.v1", source)
        self.assertIn("desktop_network_join_import_result.v1", source)
        self.assertIn("desktop_network_coordinator_discovery.v1", source)
        self.assertIn("confirm_create", source)
        self.assertIn("confirm_rotate", source)
        self.assertIn("confirm_import", source)
        self.assertIn("navigator.clipboard.writeText", source)
        self.assertIn("postNetworkRoute(route, { timeout_seconds: 2 })", source)
        self.assertIn("postNetworkRoute(route, request)", source)
        self.assertNotIn('apiPost("/api/network/worker/discover-coordinators"', source)
        self.assertNotIn('apiPost("/api/network/worker/test-connection"', source)
        self.assertNotIn('apiPost("/api/network/coordinator/join-blob"', source)
        self.assertNotIn('apiPost("/api/network/worker/join-cluster"', source)
        self.assertNotIn("/api/network/coordinator/start-dry-run", source)
        self.assertNotIn("/api/network/worker/stop", source)
        self.assertIn("Confirmed lifecycle command was cancelled", source)
        self.assertIn("confirm_start", source)
        self.assertIn("confirm_stop", source)
        self.assertIn('"/api/network/workers"', source)
        self.assertIn("backend-owned Network evidence and lifecycle routes", source)
        self.assertIn("network_lifecycle_contracts", source)
        self.assertIn("backend_lifecycle_routes_available_provider_guarded", source)
        self.assertIn("Mutation guardrail", source)
        self.assertIn("Lifecycle dry-run routes:", source)
        self.assertIn("confirmed lifecycle start/stop routes", source)
        self.assertIn("Setup write/secret routes:", source)
        self.assertIn("setup secret-transfer", source)
        self.assertIn("setup config-write", source)
        self.assertNotIn("mediapipeline-network-tab", source)
        self.assertNotIn("data-network-tab", source)
        self.assertIn("function networkRolePanelIds", source)
        self.assertIn("function syncNetworkRoleDashboards", source)
        self.assertIn("data-network-role-panel", source)
        self.assertIn("function networkCoordinatorOverviewModel", source)
        self.assertIn("function networkWorkerOverviewModel", source)
        self.assertIn("function renderNetworkRoleDashboards", source)
        self.assertIn("function renderNetworkStatusBanner", source)
        self.assertIn("function renderNetworkAttentionStack", source)
        self.assertIn("function renderNetworkTopologyStrip", source)
        self.assertIn("function renderNetworkActionReadinessGates", source)
        self.assertIn("function networkDiagnosticLayers", source)
        self.assertIn("diagnostic_layers", source)
        self.assertNotIn("attention_items", source)
        self.assertNotIn("worker_event_timeline", source)
        self.assertIn("url_reachable, auth_ok, paths_ok, queue_fresh, last_claim_result", source)
        self.assertIn("Last failure code", source)
        self.assertIn("CoordinatorMaxJobRetries", source)
        self.assertIn("Worker misconfigured code", source)
        self.assertIn("running_vs_saved", source)
        self.assertIn("function networkWorkerDriftStatusText", source)
        self.assertIn("function networkWorkerPolicyDivergenceStatusText", source)
        self.assertIn("Running settings drift", source)
        self.assertIn("Coordinator policy review", source)
        self.assertIn("Policy Authority", source)
        self.assertIn("function obviousWorkerCoordinatorUrlIssue", source)
        self.assertIn("coordinator_connectivity", source)
        self.assertIn("worker_coordinator_url", source)
        self.assertIn("function networkCoordinatorBindEndpoint", source)
        self.assertIn("Worker coordinator URL", source)
        self.assertIn("Coordinator bind endpoint", source)
        self.assertIn("coordinator worker list is persisted on the coordinator host", source)
        self.assertIn("function networkWorkerHasClaimEvidence", source)
        self.assertIn('return "running";', source)
        self.assertIn('return "unknown";', source)

    def test_network_view_js_does_not_render_auth_token_settings(self) -> None:
        source = _network_asset_source()

        self.assertNotIn("CoordinatorAuthToken", source)
        self.assertNotIn("WorkerAuthToken", source)
        self.assertNotIn("Coordinator auth token:", source)
        self.assertNotIn("Worker auth token:", source)
        self.assertIn("token values are hidden", source)
        self.assertIn("Coordinator token:", source)
        self.assertIn("Worker token:", source)

    def test_local_api_network_routes_are_backend_owned(self) -> None:
        network_routes = [
            (str(route["method"]).upper(), str(route["path"]), str(route.get("effect", "")))
            for route in LOCAL_API_ROUTE_CONTRACT
            if str(route["path"]).startswith("/api/network")
        ]

        self.assertEqual(
            network_routes,
            [
                ("GET", "/api/network/workers", "none"),
                ("POST", "/api/network/coordinator/start-dry-run", "none"),
                ("POST", "/api/network/coordinator/stop-dry-run", "none"),
                ("POST", "/api/network/worker/start-dry-run", "none"),
                ("POST", "/api/network/worker/stop-dry-run", "none"),
                ("POST", "/api/network/worker/test-connection", "none"),
                ("POST", "/api/network/worker/discover-coordinators", "none"),
                ("POST", "/api/network/coordinator/join-blob", "secret-transfer"),
                ("POST", "/api/network/worker/join-cluster", "config-write"),
                ("POST", "/api/network/coordinator/start", "backend-lifecycle"),
                ("POST", "/api/network/coordinator/stop", "backend-lifecycle"),
                ("POST", "/api/network/worker/start", "backend-lifecycle"),
                ("POST", "/api/network/worker/stop", "backend-lifecycle"),
            ],
        )
        routes = {str(route["path"]): route for route in LOCAL_API_ROUTE_CONTRACT}
        test_connection = routes["/api/network/worker/test-connection"]
        self.assertEqual(test_connection["method"], "POST")
        self.assertEqual(test_connection["effect"], "none")
        self.assertEqual(test_connection["owner"], "Network")
        self.assertTrue(test_connection["frontend_exposed"])
        self.assertFalse(test_connection["requires_confirmation"])
        self.assertFalse(test_connection["journaled"])
        self.assertEqual(test_connection["request_keys"], ["timeout_seconds"])
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
        self.assertEqual(discovery["data_schema"], "desktop_network_coordinator_discovery.v1")
        self.assertNotIn("network_lifecycle", discovery)

        coordinator_join = routes["/api/network/coordinator/join-blob"]
        self.assertEqual(coordinator_join["method"], "POST")
        self.assertEqual(coordinator_join["effect"], "secret-transfer")
        self.assertEqual(coordinator_join["owner"], "Network")
        self.assertTrue(coordinator_join["frontend_exposed"])
        self.assertTrue(coordinator_join["requires_confirmation"])
        self.assertFalse(coordinator_join["journaled"])
        self.assertEqual(
            coordinator_join["request_keys"],
            ["coordinator_url", "confirm_create", "rotate_token", "confirm_rotate"],
        )
        self.assertEqual(coordinator_join["data_schema"], "desktop_network_join_blob_result.v1")
        self.assertNotIn("network_lifecycle", coordinator_join)

        worker_join = routes["/api/network/worker/join-cluster"]
        self.assertEqual(worker_join["method"], "POST")
        self.assertEqual(worker_join["effect"], "config-write")
        self.assertEqual(worker_join["owner"], "Network")
        self.assertTrue(worker_join["frontend_exposed"])
        self.assertTrue(worker_join["requires_confirmation"])
        self.assertFalse(worker_join["journaled"])
        self.assertEqual(worker_join["request_keys"], ["join_blob", "confirm_import", "timeout_seconds"])
        self.assertEqual(worker_join["data_schema"], "desktop_network_join_import_result.v1")
        self.assertNotIn("network_lifecycle", worker_join)

        for route in LOCAL_API_ROUTE_CONTRACT:
            path = str(route["path"])
            if not path.startswith("/api/network/") or not route.get("network_lifecycle"):
                continue
            with self.subTest(path=path):
                is_dry_run = path.endswith("-dry-run")
                self.assertEqual(route["owner"], "Network")
                self.assertTrue(route["frontend_exposed"])
                self.assertEqual(route["requires_confirmation"], not is_dry_run)
                self.assertEqual(route["network_lifecycle"]["role"], "worker" if "/worker/" in path else "coordinator")
                self.assertEqual(route["network_lifecycle"]["action"], "stop" if "/stop" in path else "start")
                self.assertEqual(route["network_lifecycle"]["dry_run"], is_dry_run)


if __name__ == "__main__":
    unittest.main()
