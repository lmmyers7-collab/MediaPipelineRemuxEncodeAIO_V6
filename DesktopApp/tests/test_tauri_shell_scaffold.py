from __future__ import annotations

import json
import re
import sys
import tomllib
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api.contract_command import LOCAL_API_COMMAND_ROUTE_CONTRACT
from mediapipeline_desktop_app.api.contract_read import LOCAL_API_READ_ROUTE_CONTRACT


PROJECT_ROOT = Path(__file__).resolve().parents[2]
TAURI_ROOT = PROJECT_ROOT / "DesktopApp" / "tauri_shell"
TAURI_SRC_ROOT = TAURI_ROOT / "src-tauri" / "src"
ACTIVE_SOURCE_SUFFIXES = {".html", ".js", ".py", ".ps1", ".rs"}
RELEASE_BUILD_SCRIPT = PROJECT_ROOT / "scripts" / "release" / "build.ps1"
RELEASE_TEST_SCRIPT = PROJECT_ROOT / "scripts" / "release" / "test.ps1"


def _tauri_rust_source() -> str:
    """Return all Tauri shell Rust sources as one static-audit surface."""
    return "\n".join(path.read_text(encoding="utf-8") for path in sorted(TAURI_SRC_ROOT.rglob("*.rs")))


class TauriShellScaffoldTests(unittest.TestCase):
    def test_active_v6_sources_do_not_reference_removed_tk_shell(self) -> None:
        removed_shell_terms = re.compile(
            r"CustomTkinter|customtkinter|Custom Tkinter|custom tkinter|"
            r"fallback_tk|Tk app|Tk shell|Tk Schedule|Tk main|\btkinter\b|\bTk\b"
        )
        scan_roots = (
            PROJECT_ROOT / "DesktopApp" / "mediapipeline_desktop_app",
            PROJECT_ROOT / "DesktopApp" / "tauri_shell" / "src-tauri" / "src",
            PROJECT_ROOT / "Pipeline" / "Modules",
            PROJECT_ROOT / "SmokeTests",
        )
        scan_files = [
            RELEASE_BUILD_SCRIPT,
            RELEASE_TEST_SCRIPT,
            PROJECT_ROOT / "scripts" / "operator" / "New-RealMediaValidationWorksheet.ps1",
        ]
        for root in scan_roots:
            scan_files.extend(
                path
                for path in root.rglob("*")
                if path.is_file() and path.suffix.lower() in ACTIVE_SOURCE_SUFFIXES
            )

        offenders: list[str] = []
        for path in sorted(set(scan_files)):
            if not path.exists():
                continue
            text = path.read_text(encoding="utf-8")
            for line_number, line in enumerate(text.splitlines(), start=1):
                if removed_shell_terms.search(line):
                    relative = path.relative_to(PROJECT_ROOT)
                    offenders.append(f"{relative}:{line_number}: {line.strip()}")

        self.assertEqual(offenders, [])

    def test_tauri_shell_scaffold_files_exist(self) -> None:
        for relative in (
            "package.json",
            "package-lock.json",
            "README.md",
            "Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1",
            "Test-TauriShell-Prereqs.ps1",
            "Test-TauriShell-Build.ps1",
            "Test-TauriShell-Launch.ps1",
            "Test-TauriShell-ProductionSurface.ps1",
            "New-TauriShell-PG3CleanMachineReport.ps1",
            "frontend/index.html",
            "src-tauri/Cargo.toml",
            "src-tauri/Cargo.lock",
            "src-tauri/build.rs",
            "src-tauri/tauri.conf.json",
            "src-tauri/capabilities/default.json",
            "src-tauri/icons/icon.ico",
            "src-tauri/src/main.rs",
            "src-tauri/src/lib.rs",
            "src-tauri/src/single_instance_guard.rs",
        ):
            self.assertTrue((TAURI_ROOT / relative).exists(), relative)

    def test_tauri_config_points_at_static_frontend_and_dynamic_window(self) -> None:
        config = json.loads((TAURI_ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))

        self.assertEqual(config["productName"], "MediaPipelineRemuxEncodeAIO V6")
        self.assertEqual(config["build"]["frontendDist"], "../frontend")
        self.assertEqual(config["app"]["windows"], [])
        csp = config["app"]["security"]["csp"]
        self.assertIsInstance(csp, str)
        self.assertIn("default-src 'self'", csp)
        self.assertIn("connect-src 'self'", csp)
        self.assertIn("object-src 'none'", csp)
        self.assertIn("frame-ancestors 'none'", csp)
        self.assertIn("form-action 'none'", csp)

    def test_tauri_package_lock_matches_package_identity(self) -> None:
        package = json.loads((TAURI_ROOT / "package.json").read_text(encoding="utf-8"))
        package_lock = json.loads((TAURI_ROOT / "package-lock.json").read_text(encoding="utf-8"))
        root_package = package_lock["packages"][""]

        self.assertEqual(package_lock["name"], package["name"])
        self.assertEqual(package_lock["version"], package["version"])
        self.assertEqual(root_package["name"], package["name"])
        self.assertEqual(root_package["version"], package["version"])

    def test_tauri_rust_manifest_declares_backend_launcher_dependencies(self) -> None:
        cargo = tomllib.loads((TAURI_ROOT / "src-tauri" / "Cargo.toml").read_text(encoding="utf-8"))
        lock_text = (TAURI_ROOT / "src-tauri" / "Cargo.lock").read_text(encoding="utf-8")

        self.assertEqual(cargo["package"]["name"], "mediapipeline-tauri-shell")
        self.assertIn("tauri", cargo["dependencies"])
        self.assertIn("serde_json", cargo["dependencies"])
        self.assertIn("url", cargo["dependencies"])
        self.assertIn("windows-sys", cargo["dependencies"])
        self.assertIn('name = "tauri"', lock_text)

    def test_tauri_shell_rust_launches_python_local_api_not_pipeline_directly(self) -> None:
        source = _tauri_rust_source()

        self.assertIn("mediapipeline_desktop_app.local_api_main", source)
        self.assertIn('.arg("--shell-surface")', source)
        self.assertIn('.arg("tauri")', source)
        self.assertIn('.arg("--emit-startup-progress")', source)
        self.assertIn("desktop_local_api_bootstrap.v1", source)
        self.assertIn("MEDIA_PIPELINE_TAURI_TEST_AUTOMATION", source)
        self.assertIn("pg2-webview-launch", source)
        self.assertIn("pg2-sample-validation-append", source)
        self.assertIn("MEDIA_PIPELINE_TAURI_TEST_AUTOLAUNCH_SINGLE_FILE", source)
        self.assertIn('button.click();', source)
        self.assertIn("WebviewWindowBuilder", source)
        self.assertNotIn("MediaPipeline.ps1", source)
        self.assertNotIn('.arg("ffmpeg")', source.casefold())
        self.assertNotIn("command::new(\"ffmpeg", source.casefold())
        self.assertNotIn("command::new('ffmpeg", source.casefold())

    def test_tauri_shell_drains_backend_pipes_and_cleans_up_failed_bootstrap(self) -> None:
        source = _tauri_rust_source()

        self.assertIn("spawn_backend_stdout_reader(stdout)", source)
        self.assertIn("spawn_pipe_drain(stderr", source)
        self.assertIn("read_backend_bootstrap(&rx, Duration::from_secs(20))", source)
        self.assertIn("validate_backend_health(&bootstrap.url, &bootstrap.token)", source)
        self.assertIn("recv_timeout(remaining)", source)
        self.assertIn("terminate_child(&mut child)", source)
        self.assertIn("Failed reading backend bootstrap payload", source)
        self.assertIn("Timed out waiting for backend bootstrap payload", source)
        self.assertIn("RecvTimeoutError::Disconnected", source)
        self.assertIn("Backend stdout closed before bootstrap payload was received", source)
        self.assertIn("const MAX_BOOTSTRAP_STDOUT_LINES: usize = 5", source)
        self.assertIn("const MAX_BOOTSTRAP_STDOUT_CHARS: usize = 500", source)
        self.assertIn("push_bootstrap_stdout_context(&mut stdout_context, trimmed)", source)
        self.assertIn("fn bootstrap_error", source)
        self.assertIn("Recent stdout before bootstrap", source)
        self.assertIn("fn redact_bootstrap_stdout", source)
        self.assertIn("fn redact_json_string_field", source)
        self.assertIn("let redacted_bootstrap_stdout = redact_bootstrap_stdout(trimmed)", source)
        self.assertIn("bounded_text(&redacted_bootstrap_stdout, MAX_BOOTSTRAP_STDOUT_CHARS)", source)
        self.assertIn("[mediapipeline-backend:stdout-before-bootstrap]", source)
        self.assertIn("[mediapipeline-backend:{stream_name}]", source)
        self.assertIn("[mediapipeline-backend:stdout]", source)

    def test_tauri_shell_monitors_backend_lifecycle_after_window_open(self) -> None:
        source = _tauri_rust_source()

        self.assertIn("mod backend_lifecycle_monitor", source)
        self.assertIn("start_backend_lifecycle_monitor(app.app_handle().clone())", source)
        self.assertIn('BACKEND_LIFECYCLE_EVENT: &str = "mediapipeline://backend-lifecycle"', source)
        self.assertIn("BACKEND_HEALTH_MONITOR_INTERVAL: Duration = Duration::from_secs(5)", source)
        self.assertIn("BACKEND_HEALTH_FAILURE_THRESHOLD: usize = 2", source)
        self.assertIn("mediapipeline_backend_lifecycle_event.v1", source)
        self.assertIn("try_take_exited", source)
        self.assertIn("health_check", source)
        self.assertIn("Backend process exited unexpectedly with code", source)
        self.assertIn("Backend lifecycle health check failed", source)
        self.assertIn("backend_health_failed", source)
        self.assertIn("app_handle.emit(BACKEND_LIFECYCLE_EVENT", source)

    def test_tauri_shell_rejects_second_instance_and_exposes_read_only_lifecycle_banner(self) -> None:
        source = _tauri_rust_source()
        audit = (TAURI_ROOT / "Test-TauriShell-ProductionSurface.ps1").read_text(encoding="utf-8")
        static_root = PROJECT_ROOT / "DesktopApp" / "mediapipeline_desktop_app" / "ui_web" / "static"
        index = (static_root / "index.html").read_text(encoding="utf-8")
        bridge = (static_root / "assets" / "tauriLifecycleBridge.js").read_text(encoding="utf-8")
        app_js = (static_root / "assets" / "app.js").read_text(encoding="utf-8")

        self.assertIn("mod single_instance_guard", source)
        self.assertIn("acquire_single_instance_guard()?", source)
        self.assertIn("Local\\\\MediaPipelineRemuxEncodeAIO_V6_TauriShell", source)
        self.assertIn("ERROR_ALREADY_EXISTS", source)
        self.assertIn("Another MediaPipeline Tauri/WebView2 shell instance is already running", source)
        self.assertIn('/assets/tauriLifecycleBridge.js', index)
        self.assertIn("mediapipeline://backend-lifecycle", bridge)
        self.assertIn("eventApi.listen", bridge)
        self.assertIn("window.dispatchEvent(new CustomEvent", bridge)
        self.assertIn('window.addEventListener("mediapipeline:backend-lifecycle", handleTauriBackendLifecycleEvent)', app_js)
        self.assertIn("tauri-lifecycle-alert", app_js)
        self.assertIn("Open Diagnostics before starting, draining, saving, renaming, publishing, or closing.", app_js)
        self.assertIn("app.windows empty", audit)
        self.assertIn("CSP configured", audit)
        self.assertIn("no static production devtools flags", audit)
        self.assertIn("no token-adjacent runtime logging", audit)
        self.assertIn("Get-ChildItem -LiteralPath $srcRoot -Filter '*.rs' -Recurse -File", audit)
        self.assertIn("read-only Tauri lifecycle event bridge", audit)

    def test_tauri_shell_startup_errors_include_bounded_operator_context(self) -> None:
        source = _tauri_rust_source()

        self.assertIn("const MAX_OPERATOR_PATH_CHARS: usize = 320", source)
        self.assertIn("fn display_bounded_path", source)
        self.assertIn("fn format_path_candidates", source)
        self.assertIn("Could not locate DesktopApp root for the Python backend. Development root checked", source)
        self.assertIn("packaged candidates checked", source)
        self.assertIn("Bundled Python runtime was not found for DesktopApp root", source)
        self.assertIn("Backend stdout was not captured after starting Python backend", source)
        self.assertIn("Backend stderr was not captured after starting Python backend", source)
        self.assertIn("Backend health validation failed for", source)
        self.assertIn("Backend route contract validation failed for", source)
        self.assertNotIn("token}", source.replace("Authorization: Bearer {token}", ""))

    def test_tauri_shell_validates_backend_health_contract_before_opening_window(self) -> None:
        source = _tauri_rust_source()

        self.assertIn('"/api/health"', source)
        self.assertIn("desktop_backend_health.v1", source)
        self.assertIn("Backend health response was not JSON", source)
        self.assertIn("Backend health status is not ok", source)
        self.assertIn("Backend health is missing required capability", source)
        self.assertIn("backend reported capabilities", source)
        self.assertIn("fn format_list_preview", source)
        for capability in (
            "snapshot",
            "telemetry",
            "diagnostics",
            "close-readiness",
            "command-history",
            "settings-workspace",
            "settings-validate",
            "pipeline-start",
            "audit-start",
            "rerun-start",
        ):
            self.assertIn(f'"{capability}"', source)

    def test_tauri_shell_validates_local_api_route_contract_before_opening_window(self) -> None:
        source = _tauri_rust_source()

        self.assertIn("struct BackendContract", source)
        self.assertIn("struct BackendRoute", source)
        self.assertIn("validate_backend_contract(&bootstrap.url, &bootstrap.token)", source)
        self.assertIn('"/api/contract"', source)
        self.assertIn("desktop_local_api_contract.v1", source)
        self.assertIn("Backend contract response was not JSON", source)
        self.assertIn("Unexpected backend contract schema", source)
        self.assertIn("Backend contract is missing required route", source)
        self.assertIn("auth_required={auth_required}", source)
        self.assertIn("backend reported {} route(s); sample", source)
        self.assertIn("fn format_route_sample", source)
        for route in (
            "/api/snapshot",
            "/api/telemetry",
            "/api/diagnostics",
            "/api/backend/close-readiness",
            "/api/settings/pipeline-plan-preview",
            "/api/settings/save-patch",
            "/api/pipeline/start",
            "/api/backend/shutdown",
        ):
            self.assertIn(f'"{route}"', source)

    def test_tauri_shell_validates_backend_served_webview_before_opening_window(self) -> None:
        source = _tauri_rust_source()

        self.assertIn("validate_backend_web_ui(&bootstrap.url, &bootstrap.token)", source)
        self.assertIn("fn validate_backend_web_ui", source)
        self.assertIn('"GET", "/", token', source)
        self.assertIn(
            "tauri_bootstrap_initialization_script(backend.token(), backend.startup_warnings())",
            source,
        )
        self.assertIn(".initialization_script(initialization_script)", source)
        self.assertIn("window.MEDIA_PIPELINE_TAURI_BOOTSTRAP", source)
        self.assertIn("startupWarnings", source)
        self.assertIn("Backend WebView asset validation warning", source)
        self.assertIn("web_ui_validation_error_is_fatal", source)
        self.assertIn('"/assets/app.js"', source)
        self.assertIn('"/assets/crossPageContextView.js"', source)
        self.assertIn('"/assets/crossPageContextView.conflict.js"', source)
        self.assertIn('"/assets/crossPageContextView.sample.js"', source)
        self.assertIn('"/assets/crossPageContextView.settings.js"', source)
        self.assertIn('"/assets/crossPageContextView.sampleValidation.worksheet.js"', source)
        self.assertIn('"/assets/crossPageContextView.sampleValidation.runbook.js"', source)
        self.assertIn('"/assets/crossPageContextView.sampleValidation.records.js"', source)
        self.assertIn('"/assets/crossPageContextView.sampleValidation.js"', source)
        self.assertIn('"/assets/diagnosticsView.activejobs.js"', source)
        self.assertIn('"/assets/diagnosticsView.log.js"', source)
        self.assertIn('"/assets/diagnosticsView.investigation.js"', source)
        self.assertIn('"/assets/diagnosticsView.js"', source)
        self.assertIn('"/assets/settingsView.rawTriage.js"', source)
        self.assertIn('"/assets/settingsView.safetyLocks.js"', source)
        self.assertIn('"/assets/settings/patchReview.js"', source)
        self.assertIn('"/assets/settingsView.js"', source)
        self.assertIn('"/assets/settingsOverview.js"', source)
        self.assertIn('"/assets/launchView.risk.js"', source)
        self.assertIn('"/assets/launchView.scope.js"', source)
        self.assertIn('"/assets/launchView.realmedia.js"', source)
        self.assertIn('"/assets/launchView.preflight.js"', source)
        self.assertIn('"/assets/launchView.js"', source)
        self.assertIn('"/assets/pendingPublishView.recovery.js"', source)
        self.assertIn('"/assets/pendingPublishView.diagnostics.js"', source)
        self.assertIn('"/assets/pendingPublishView.drain.js"', source)
        self.assertIn('"/assets/pendingPublishView.confidence.js"', source)
        self.assertIn('"/assets/diagnosticsStateSummaryView.js"', source)
        self.assertIn("window.MEDIA_PIPELINE_BOOTSTRAP = Object.assign(", source)
        self.assertIn("Backend WebView index leaked the bearer token", source)
        self.assertIn("id=\\\"cross-page-real-media-status\\\"", source)
        self.assertIn("id=\\\"cross-page-real-media-rows\\\"", source)
        self.assertIn("id=\\\"sample-validation-status\\\"", source)
        self.assertIn("id=\\\"sample-validation-cutover-status\\\"", source)
        self.assertIn("id=\\\"sample-validation-cutover-rows\\\"", source)
        self.assertIn("id=\\\"sample-validation-sample-set-status\\\"", source)
        self.assertIn("id=\\\"sample-validation-sample-set-rows\\\"", source)
        self.assertIn("id=\\\"sample-validation-category\\\"", source)
        self.assertIn("id=\\\"sample-validation-use-sample-set-category-button\\\"", source)
        self.assertIn("id=\\\"home-external-dependencies-status\\\"", source)
        self.assertIn("id=\\\"home-external-dependencies-summary\\\"", source)
        self.assertIn("id=\\\"settings-backend-media-policy-status\\\"", source)
        self.assertIn("id=\\\"settings-backend-media-policy-rows\\\"", source)
        self.assertIn("id=\\\"settings-policy-delta-rows\\\"", source)
        self.assertIn("id=\\\"settings-effective-policy-rows\\\"", source)
        self.assertIn("id=\\\"settings-effective-policy-detail\\\"", source)
        self.assertIn("id=\\\"settings-handbrake-preview-status\\\"", source)
        self.assertIn("id=\\\"settings-handbrake-decision\\\"", source)
        self.assertIn("NOT EVALUATED", source)
        self.assertIn("id=\\\"settings-handbrake-active-preset\\\"", source)
        self.assertIn("id=\\\"settings-builder-routing-profile\\\"", source)
        self.assertIn("id=\\\"settings-builder-output-container\\\"", source)
        self.assertIn("id=\\\"launch-settings-risk-rows\\\"", source)
        self.assertIn("id=\\\"diagnostics-state-triage-status\\\"", source)
        self.assertIn("id=\\\"diagnostics-close-readiness\\\"", source)
        self.assertIn("id=\\\"backend-lifecycle-summary\\\"", source)
        self.assertIn("id=\\\"backend-shutdown-button\\\"", source)
        self.assertIn("/api/sample-validation?limit=10", source)
        self.assertIn("/api/sample-validation/append", source)
        self.assertIn("function renderBackendLifecycle", source)
        self.assertIn("async function requestBackendShutdown", source)
        self.assertIn("/api/backend/shutdown", source)
        self.assertIn("Backend shutdown is disabled in WebView until close-readiness reports safe", source)
        self.assertIn("function renderExternalDependencyDigest", source)
        self.assertIn("function externalDependencyRows", source)
        self.assertIn("External dependency readiness", source)
        self.assertIn("Resolve blocked Settings OCR or Maintenance toolchain evidence", source)
        self.assertIn("function renderDiagnosticsStateTriage", source)
        self.assertIn("function renderDiagnosticsStateTriageRows", source)
        self.assertIn("Backend read order:", source)
        self.assertIn("settings: values.settings || getLastSettings()", source)
        self.assertIn("function renderCrossPageRealMediaWorksheet", source)
        self.assertIn("function crossPageRealMediaWorksheetRows", source)
        self.assertIn("function buildSampleValidationRequest", source)
        self.assertIn("function renderSampleValidationCutoverGate", source)
        self.assertIn("WebView cutover gate:", source)
        self.assertIn("function renderSampleValidationSampleSetGuide", source)
        self.assertIn("function useSelectedSampleSetCategory", source)
        self.assertIn("Recommended real-media sample set:", source)
        self.assertIn("function crossPageSettingsPolicyEvidence", source)
        self.assertIn("function settingsBackendMediaPolicyReadiness", source)
        self.assertIn("function renderSettingsBackendMediaPolicyReadiness", source)
        self.assertIn("settings-backend-result-rows", source)
        self.assertIn("function renderHandbrakePreviewSummary", source)
        self.assertIn("function collectSettingsBuilderPatch", source)
        self.assertIn("RoutingProfile: settingsBuilderInputValue(\\\"settings-builder-routing-profile\\\")", source)
        self.assertIn("OutputContainer: settingsBuilderInputValue(\\\"settings-builder-output-container\\\")", source)
        self.assertIn("Source-specific route previews are not exposed in Settings", source)
        self.assertNotIn("id=\\\"settings-source-media-json\\\"", source)
        self.assertNotIn("id=\\\"settings-preview-plan-button\\\"", source)
        self.assertNotIn("id=\\\"settings-source-facts-rows\\\"", source)
        self.assertNotIn("bindSettingsClick(\\\"settings-preview-plan-button\\\", addSettingsEventHandlers.previewSettingsPipelinePlan)", source)
        self.assertNotIn("function parseSettingsSourceMediaJson", source)
        self.assertNotIn("function renderSettingsPipelinePlanPreview", source)
        self.assertNotIn("async function previewSettingsPipelinePlan", source)
        self.assertNotIn("source_media: sourceMedia", source)
        self.assertIn("function settingsPolicyDeltaRows", source)
        self.assertIn("Staged media-policy delta:", source)
        self.assertIn("function settingsEffectivePolicyRows", source)
        self.assertIn("Effective policy trust summary:", source)
        self.assertIn("Launch-active policy is the saved backend config", source)
        self.assertIn("function settingsBackendResultRows", source)
        self.assertIn("function settingsBackendResultDetailLines", source)
        self.assertIn("id=\\\"settings-backend-result-detail\\\"", source)
        self.assertIn("function renderSettingsBackendResultFromEntries", source)
        self.assertIn("Patch JSON changed after the last preview. Preview again before saving.", source)
        self.assertIn("Save Patch is the only persistence command", source)
        self.assertIn("function settingsMediaPolicyReadinessLine", source)
        self.assertIn("Resolve blocked saved media-policy rows before launching unattended work.", source)
        self.assertIn("Backend WebView asset validation failed", source)
        self.assertIn("Backend WebView index still contains the raw bootstrap placeholder", source)
        self.assertIn("Backend WebView cross-page script is missing required fragment", source)
        self.assertIn("Backend WebView diagnostics script is missing required fragment", source)
        self.assertIn("Backend WebView settings patch-review script is missing required fragment", source)
        self.assertIn("Backend WebView settings script is missing required fragment", source)
        self.assertIn("Backend WebView settings policy-impact script is missing required fragment", source)
        self.assertIn("Backend WebView settings overview script is missing required fragment", source)
        self.assertIn("Backend WebView launch script is missing required fragment", source)
        self.assertIn("Backend WebView diagnostics state script is missing required fragment", source)

    def test_tauri_shell_required_routes_match_python_local_api_contract(self) -> None:
        source = _tauri_rust_source()
        match = re.search(
            r"REQUIRED_ROUTES:\s*&\[\(&str,\s*&str,\s*bool\)\]\s*=\s*&\[(.*?)\];",
            source,
            re.S,
        )
        self.assertIsNotNone(match)
        rust_routes = set(
            re.findall(
                r'\("([^"]+)",\s*"([^"]+)",\s*(true|false)\)',
                match.group(1),
            )
        )
        expected_routes = {
            (
                str(route["method"]),
                str(route["path"]),
                "true" if bool(route["auth_required"]) else "false",
            )
            for route in LOCAL_API_READ_ROUTE_CONTRACT + LOCAL_API_COMMAND_ROUTE_CONTRACT
        }

        self.assertEqual(rust_routes, expected_routes)

    def test_tauri_shell_checks_close_readiness_before_shutdown(self) -> None:
        source = _tauri_rust_source()

        self.assertIn("struct CloseReadiness", source)
        self.assertIn("safe_to_close: bool", source)
        self.assertIn("state: String", source)
        self.assertIn("reason: String", source)
        self.assertIn("warnings: Vec<String>", source)
        self.assertIn("continuous_watcher: ContinuousWatcher", source)
        self.assertIn("struct ContinuousWatcher", source)
        self.assertIn("status: String", source)
        self.assertIn("stop_requested: bool", source)
        self.assertIn("generation: u64", source)
        self.assertIn("request_close_readiness(&backend.url, &backend.token)", source)
        self.assertIn("/api/backend/close-readiness", source)
        self.assertIn("desktop_close_readiness.v1", source)
        self.assertIn('Ok(readiness) if readiness.safe_to_close => true', source)
        self.assertIn("Unexpected close-readiness schema", source)
        self.assertIn("Authorization: Bearer {token}", source)
        self.assertIn("confirm_close_if_needed(window)", source)
        self.assertIn("api.prevent_close()", source)
        self.assertIn("MessageBoxW", source)
        self.assertIn("Close readiness could not be verified", source)
        self.assertIn("This is not treated as safe", source)
        self.assertIn("readiness.reason.trim().is_empty()", source)
        self.assertIn("Backend reports active work. Current state: {}", source)
        self.assertIn("FORCE_CLOSE_RECOVERY_WARNING", source)
        self.assertIn("The backend will be asked to stop app-owned pipeline work before shutdown", source)

    def test_tauri_shell_close_readiness_prompt_includes_bounded_backend_warnings_and_watcher_evidence(self) -> None:
        source = _tauri_rust_source()

        self.assertIn("#[serde(default)]", source)
        self.assertIn("const MAX_CLOSE_READINESS_WARNINGS: usize = 5", source)
        self.assertIn("const MAX_CLOSE_READINESS_WARNING_CHARS: usize = 240", source)
        self.assertIn("fn close_readiness_warning_detail", source)
        self.assertIn("fn close_readiness_watcher_lines", source)
        self.assertIn("let detail = close_readiness_warning_detail(&readiness)", source)
        self.assertIn("Warnings:", source)
        self.assertIn("take(MAX_CLOSE_READINESS_WARNINGS)", source)
        self.assertIn("bounded_text(warning.trim(), MAX_CLOSE_READINESS_WARNING_CHARS)", source)
        self.assertIn("Continuous schedule-stop watcher:", source)
        self.assertIn("generation: {}", source)
        self.assertIn("closing the backend would remove this in-process stop-at-schedule-boundary guard", source)
        self.assertIn("status.eq_ignore_ascii_case(\"armed\")", source)

    def test_tauri_shell_requests_graceful_backend_shutdown_before_kill(self) -> None:
        source = _tauri_rust_source()

        self.assertIn("request_backend_shutdown(&self.url, &self.token)", source)
        self.assertIn("on_window_event", source)
        self.assertIn("WindowEvent::CloseRequested", source)
        self.assertIn("RunEvent::ExitRequested", source)
        self.assertIn("RunEvent::Exit", source)
        self.assertIn("shutdown_backend_state(app_handle)", source)
        self.assertIn("backend.shutdown()", source)
        self.assertIn('"/api/backend/shutdown"', source)
        self.assertIn('"POST"', source)
        self.assertIn('"force_active_work_shutdown":true', source)
        self.assertIn("Authorization: Bearer {token}", source)
        self.assertIn("wait_for_child_exit(&mut child, Duration::from_secs(3))", source)
        self.assertIn("terminate_child(&mut child)", source)
        self.assertIn("backend shutdown request failed", source)
        self.assertIn("backend did not exit within grace period; terminating process", source)
        self.assertIn("backend process kill failed", source)
        self.assertIn("backend process wait after kill failed", source)
        self.assertIn("token: String", source)
        self.assertIn("url: String", source)

    def test_tauri_shell_caps_backend_http_responses(self) -> None:
        source = _tauri_rust_source()

        self.assertIn("const MAX_BACKEND_RESPONSE_BYTES: usize = 16 * 1024 * 1024", source)
        self.assertIn("fn read_backend_response_capped", source)
        self.assertIn("response.len().saturating_add(count) > max_bytes", source)
        self.assertIn("Backend response exceeded {max_bytes} byte limit.", source)
        self.assertIn("Backend response was not UTF-8", source)
        self.assertIn("read_backend_response_capped(&mut stream, MAX_BACKEND_RESPONSE_BYTES)", source)
        self.assertIn("fn backend_response_body_preview", source)
        self.assertIn("body: {preview}", source)
        self.assertIn("backend_response_body_preview(&response, 500)", source)
        self.assertNotIn("stream.read_to_string(&mut response)", source)

    def test_tauri_shell_has_failure_injection_tests_for_backend_helpers(self) -> None:
        source = _tauri_rust_source()

        self.assertIn("fn serve_once", source)
        self.assertIn("TcpListener::bind(\"127.0.0.1:0\")", source)
        self.assertIn("read_backend_response_capped_rejects_oversized_and_invalid_utf8", source)
        self.assertIn("request_backend_json_success_sends_expected_request_without_frontend_bypass", source)
        self.assertIn("request_backend_json_rejects_non_200_with_bounded_body_preview", source)
        self.assertIn("request_backend_json_rejects_missing_body_and_non_http_url", source)
        self.assertIn("validate_backend_health_missing_capability_reports_sample_without_token", source)
        self.assertIn("validate_backend_contract_missing_route_reports_route_sample_without_token", source)
        self.assertIn("validate_backend_web_ui_requires_index_and_real_media_assets_without_leaking_token", source)
        self.assertIn("validate_backend_web_ui_reports_missing_fragments_without_token", source)
        self.assertIn("assert!(!error.contains(\"secret-token\"))", source)

    def test_tauri_prereq_checker_is_non_destructive(self) -> None:
        source = (TAURI_ROOT / "Test-TauriShell-Prereqs.ps1").read_text(encoding="utf-8")

        self.assertIn("RequireToolchain", source)
        self.assertIn("RequireBuildTools", source)
        self.assertIn("CheckOnly", source)
        self.assertIn("CheckOnly mode: verifying layout/runtime prerequisites only", source)
        self.assertIn("preview prerequisite check", source)
        self.assertIn("This check is non-mutating and does not replace the V5 fallback workspace", source)
        self.assertIn("function Resolve-TauriPython", source)
        self.assertIn("Backend Python runtime", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe or Pipeline\\Runtime\\Python\\python.exe missing", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("local_api_main --help", source)
        self.assertIn("Next validation: run Test-TauriShell-Build.ps1", source)
        self.assertIn("This prereq check does not open WebView2 or process media", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)

    def test_release_self_test_runs_preview_prereqs_without_requiring_toolchain(self) -> None:
        source = RELEASE_TEST_SCRIPT.read_text(encoding="utf-8")
        policy_source = (PROJECT_ROOT / "scripts" / "release" / "release_policy.ps1").read_text(encoding="utf-8")

        self.assertIn("$tauriPrereqs", source)
        self.assertIn("Test-TauriShell-Prereqs.ps1", source)
        self.assertIn("Tauri Preview Gate", source)
        self.assertIn("Tauri shell preview prerequisites", source)
        self.assertIn("SmokeTests", source)
        self.assertIn("Smoke test inventory", source)
        self.assertIn("Docs\\inventories\\SMOKE_TEST_INVENTORY.md", source)
        self.assertIn("SmokeTests\\Test-WebViewRealMediaEvidenceSmoke.ps1", source)
        self.assertIn("SmokeTests WebView evidence smoke", source)
        self.assertIn("Test-WebViewRealMediaEvidenceSmoke.ps1", source)
        self.assertIn("SmokeTests WebView command evidence smoke", source)
        self.assertIn("Test-WebViewCommandEvidenceSmoke.ps1", source)
        self.assertIn("SmokeTests WebView row detail smoke", source)
        self.assertIn("Test-WebViewRowDetailSmoke.ps1", source)
        self.assertIn("SmokeTests WebView schedule smoke", source)
        self.assertIn("Test-WebViewScheduleSmoke.ps1", source)
        self.assertIn("SmokeTests WebView browser schedule smoke", source)
        self.assertIn("Test-WebViewBrowserScheduleSmoke.ps1", source)
        self.assertIn("SmokeTests WebView browser backend lifecycle smoke", source)
        self.assertIn("Test-WebViewBrowserLifecycleSmoke.ps1", source)
        self.assertIn("SmokeTests local API lifecycle contract smoke", source)
        self.assertIn("Test-LocalApiLifecycleContractSmoke.ps1", source)
        self.assertIn("SmokeTests local API Maintenance dry-run contract smoke", source)
        self.assertIn("Test-LocalApiMaintenanceDryRunContractSmoke.ps1", source)
        self.assertIn("SmokeTests local API sample validation contract smoke", source)
        self.assertIn("Test-LocalApiSampleValidationContractSmoke.ps1", source)
        self.assertIn("SmokeTests WebView browser high-risk smoke", source)
        self.assertIn("Test-WebViewBrowserHighRiskSmoke.ps1", source)
        self.assertIn("SmokeTests WebView browser diagnostics handoff smoke", source)
        self.assertIn("Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1", source)
        self.assertIn("SmokeTests WebView browser pending drain guard smoke", source)
        self.assertIn("Test-WebViewBrowserPendingDrainGuardSmoke.ps1", source)
        self.assertIn("SmokeTests WebView browser completed pending proof smoke", source)
        self.assertIn("Test-WebViewBrowserCompletedPendingProofSmoke.ps1", source)
        self.assertIn("SmokeTests WebView browser large daily-table smoke", source)
        self.assertIn("Test-WebViewBrowserLargeTableSmoke.ps1", source)
        self.assertIn("SmokeTests WebView browser rename smoke", source)
        self.assertIn("Test-WebViewBrowserRenameSmoke.ps1", source)
        self.assertIn("SmokeTests WebView browser network smoke", source)
        self.assertIn("Test-WebViewBrowserNetworkSmoke.ps1", source)
        self.assertIn("SmokeTests WebView browser telemetry smoke", source)
        self.assertIn("Test-WebViewBrowserTelemetrySmoke.ps1", source)
        self.assertIn("SmokeTests WebView browser Maintenance/Reports smoke", source)
        self.assertIn("Test-WebViewBrowserMaintenanceReportsSmoke.ps1", source)
        self.assertIn("SmokeTests WebView browser Sample Validation smoke", source)
        self.assertIn("Test-WebViewBrowserSampleValidationSmoke.ps1", source)
        self.assertIn("SmokeTests WebView browser Home live-state smoke", source)
        self.assertIn("Test-WebViewBrowserHomeLiveStateSmoke.ps1", source)
        self.assertIn("SmokeTests WebView browser Launch/Queue readiness smoke", source)
        self.assertIn("Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1", source)
        self.assertIn("SmokeTests WebView browser layout manager smoke", source)
        self.assertIn("Test-WebViewBrowserLayoutManagerSmoke.ps1", source)
        self.assertIn("SmokeTests WebView rename readiness smoke", source)
        self.assertIn("Test-WebViewRenameReadinessSmoke.ps1", source)
        self.assertIn("SmokeTests WebView browser settings/launch smoke", source)
        self.assertIn("Test-WebViewBrowserSettingsLaunchSmoke.ps1", source)
        self.assertNotIn("Root real-media validation worksheet helper", source)
        self.assertIn("Canonical real-media validation worksheet helper", source)
        self.assertIn("New-RealMediaValidationWorksheet.ps1", source)
        self.assertIn("SmokeTests WebView settings launch policy smoke", source)
        self.assertIn("Test-WebViewSettingsLaunchPolicySmoke.ps1", source)
        self.assertIn("SmokeTests WebView settings live-config smoke", source)
        self.assertIn("Test-WebViewSettingsLaunchLiveConfigSmoke.ps1", source)
        self.assertIn("SmokeTests WebView settings patch evidence smoke", source)
        self.assertIn("Test-WebViewSettingsPatchEvidenceSmoke.ps1", source)
        self.assertIn("Application facade sample validation mixin", source)
        self.assertIn("app\\sample_validation\\policy.py", source)
        self.assertIn("Local API sample validation command handlers", source)
        self.assertIn("tauri_preview_binary_included", source)
        self.assertIn("Import-MediaPipelineReleasePolicy", source)
        self.assertIn("Get-MediaPipelineReleaseHygieneRules", source)
        self.assertIn("Tauri preview packaged executable", policy_source)
        self.assertIn("New-MediaPipelineReleaseHygieneRule -Kind 'path_present' -RelativePath 'DesktopApp\\tauri_shell\\mediapipeline-tauri-shell.exe'", policy_source)
        self.assertIn("Tauri shell PG-3 report helper", source)
        self.assertIn("New-TauriShell-PG3CleanMachineReport.ps1", source)
        self.assertIn("PG-3 clean-machine operator reports", policy_source)
        self.assertIn("V6 WebView reliability checks", source)
        self.assertNotIn("legacyDesktopEntryPoint", source)
        self.assertIn("V6 reliability compatibility wrapper", source)
        self.assertIn("Invoke-ReliabilityRegressionChecks.ps1", source)
        self.assertIn("-ShowWarningsOnSuccess", source)
        self.assertNotIn("-RequireToolchain", source)
        self.assertNotIn("-RequireBuildTools", source)

    def test_release_builder_has_opt_in_tauri_preview_binary_packaging(self) -> None:
        source = RELEASE_BUILD_SCRIPT.read_text(encoding="utf-8")
        policy_source = (PROJECT_ROOT / "scripts" / "release" / "release_policy.ps1").read_text(encoding="utf-8")

        self.assertIn("IncludeTauriPreviewBinary", source)
        self.assertIn("src-tauri\\target\\release\\mediapipeline-tauri-shell.exe", source)
        self.assertIn("DesktopApp\\tauri_shell\\mediapipeline-tauri-shell.exe", source)
        self.assertIn("tauri_preview_binary_included", source)
        self.assertIn("Compiled Tauri preview executable was copied", source)
        self.assertIn("Run the Tauri release build first", source)
        self.assertIn("release_policy.ps1", source)
        self.assertIn("Get-MediaPipelineReleaseExclusionReason", source)
        self.assertIn("DesktopApp\\tests\\*", policy_source)
        self.assertIn("test suite omitted", policy_source)
        self.assertIn("Docs\\PG3CleanMachineReports\\*", policy_source)
        self.assertIn("operator clean-machine validation evidence omitted", policy_source)

    def test_tauri_pg3_clean_machine_report_helper_is_evidence_only(self) -> None:
        script = TAURI_ROOT / "New-TauriShell-PG3CleanMachineReport.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("PG-3 Clean-Machine Validation Report", source)
        self.assertIn("StrictCleanMachine", source)
        self.assertIn("OperatorConfirmedNoDeveloperTools", source)
        self.assertIn("Developer Tool Scan", source)
        self.assertIn("node', 'npm', 'cargo", source)
        self.assertIn("Visual Studio C++ Build Tools", source)
        self.assertIn("PG-3 can be marked proven only when this report was generated on a separate clean Windows machine", source)
        self.assertIn("Docs\\PG3CleanMachineReports", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("/api/pipeline/start", source)
        self.assertNotIn("MediaPipeline.ps1", source)

    def test_release_self_test_child_script_checks_are_bounded(self) -> None:
        source = RELEASE_TEST_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function Invoke-ReleaseScriptProcess", source)
        self.assertIn("[int]$TimeoutSeconds = 600", source)
        self.assertIn("RedirectStandardOutput = $true", source)
        self.assertIn("RedirectStandardError = $true", source)
        self.assertIn("ReadToEndAsync()", source)
        self.assertIn("WaitForExit($waitMilliseconds)", source)
        self.assertIn("$process.Kill($true)", source)
        self.assertIn("timed out after $TimeoutSeconds second(s)", source)
        self.assertIn("-TimeoutSeconds 300", source)
        self.assertIn("-TimeoutSeconds 120", source)

    def test_release_self_test_tracks_consolidated_local_api_contracts(self) -> None:
        source = RELEASE_TEST_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("api\\contract_command.py", source)
        self.assertIn("api\\contract_read.py", source)
        for removed_contract in (
            "contract_command_diagnostics.py",
            "contract_command_files.py",
            "contract_command_maintenance.py",
            "contract_command_process.py",
            "contract_command_rename.py",
            "contract_command_settings.py",
            "contract_read_inventory.py",
            "contract_read_status.py",
            "contract_read_workspace.py",
        ):
            self.assertNotIn(removed_contract, source)

    def test_release_self_test_validates_webview_static_asset_references(self) -> None:
        source = RELEASE_TEST_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function Test-WebStaticAssetReferences", source)
        self.assertIn("Web Static Asset References", source)
        self.assertIn("Web static index bootstrap placeholder is present.", source)
        self.assertIn("[regex]::Matches($html", source)
        self.assertIn('(?:src|href)="/assets/', source)
        self.assertIn("Unsafe Web static asset reference", source)
        self.assertIn("Web static index references missing assets", source)
        self.assertIn("Test-WebStaticAssetReferences -StaticRoot", source)

    def test_release_self_test_validates_api_browser_launcher_token_policy(self) -> None:
        source = RELEASE_TEST_SCRIPT.read_text(encoding="utf-8")

        self.assertIn("function Test-ApiBrowserLauncherTokenPolicy", source)
        self.assertIn("API Browser Launcher Token Policy", source)
        self.assertIn("DesktopApp\\Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1", source)
        self.assertIn("\\[switch\\]\\$NoTokenDevMode", source)
        self.assertIn("Token auth: enabled \\(browser receives a per-run bootstrap token\\)", source)
        self.assertIn("Token auth: DISABLED by explicit -NoTokenDevMode", source)
        self.assertIn("API browser launcher keeps token auth enabled by default.", source)
        self.assertIn("Test-ApiBrowserLauncherTokenPolicy", source)

    def test_reliability_gate_loads_pending_drain_summary_helpers(self) -> None:
        source = (PROJECT_ROOT / "Pipeline" / "Tests" / "Unit" / "Invoke-PendingPublishSafetyChecks.ps1").read_text(encoding="utf-8")
        pending_push = (PROJECT_ROOT / "engine" / "publish" / "pending_push.ps1").read_text(encoding="utf-8")

        self.assertIn("function Get-PendingDrainSummaryPath", source)
        self.assertIn("function Write-PendingDrainSummary", source)
        self.assertIn("function Add-PendingDrainSummaryCount", source)
        self.assertIn("function New-PendingDrainSummaryItem", source)
        self.assertIn("function Complete-PendingDrainSummary", source)
        self.assertIn("function Invoke-RetryPendingPushes", source)
        self.assertIn("Pending drain summary item helper must be defined before Invoke-RetryPendingPushes.", source)
        self.assertNotIn("Complete-PendingDrainSummary -Summary $summary -Items @($summaryItems)", pending_push)
        self.assertIn("Complete-PendingDrainSummary -Summary $summary -Items $summaryItems", pending_push)

    def test_reliability_gate_valid_config_fixture_tracks_required_safety_keys(self) -> None:
        source = (PROJECT_ROOT / "Pipeline" / "Tests" / "Invoke-ReliabilityRegressionChecks.ps1").read_text(encoding="utf-8")
        config_registry_check = (PROJECT_ROOT / "Pipeline" / "Tests" / "Unit" / "Invoke-ConfigKeyRegistryChecks.ps1").read_text(encoding="utf-8")
        config_schema = (PROJECT_ROOT / "engine" / "config" / "config_schema.ps1").read_text(encoding="utf-8")

        self.assertIn("Invoke-ConfigKeyRegistryChecks.ps1", source)
        self.assertIn("Invoke-ContractSchemaChecks.ps1", source)
        self.assertIn("MediaPipeline_config_template.psd1", config_registry_check)
        self.assertIn("ValidExtensions", config_schema)
        self.assertIn("RobocopyFlags", config_schema)
        self.assertIn("RobocopyTimeoutSeconds", config_schema)

    def test_environment_verifier_setup_validator_is_bounded(self) -> None:
        source = (PROJECT_ROOT / "scripts" / "verify-env.ps1").read_text(encoding="utf-8")

        self.assertIn("function Invoke-EnvironmentProcess", source)
        self.assertIn("RedirectStandardOutput = $true", source)
        self.assertIn("RedirectStandardError = $true", source)
        self.assertIn("ReadToEndAsync()", source)
        self.assertIn("WaitForExit($waitMilliseconds)", source)
        self.assertIn("$process.Kill($true)", source)
        self.assertIn("Setup validator timed out after $setupValidatorTimeoutSeconds second(s)", source)
        self.assertIn("$setupValidatorTimeoutSeconds = 180", source)

    def test_setup_validate_only_uses_bounded_path_probes(self) -> None:
        setup_root = PROJECT_ROOT / "Pipeline" / "Setup-MediaPipeline.ps1"
        setup_slices = PROJECT_ROOT / "Pipeline" / "Setup-MediaPipeline"
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                setup_root,
                setup_slices / "Validation.ps1",
                setup_slices / "PathValidation.ps1",
            )
        )

        self.assertIn("function Invoke-SetupValidationProbe", source)
        self.assertIn("function Test-ValidationPathExists", source)
        self.assertIn("function Test-ValidationPathWritable", source)
        self.assertIn("ReadToEndAsync()", source)
        self.assertIn("WaitForExit($waitMilliseconds)", source)
        self.assertIn("$process.Kill($true)", source)
        self.assertIn("$validationPathTimeoutSeconds = 12", source)
        self.assertIn("timed out after $validationPathTimeoutSeconds second(s) while checking path availability", source)
        self.assertIn("timed out after $validationPathTimeoutSeconds second(s) while checking writability", source)

    def test_setup_accept_defaults_missing_paths_fail_validation_instead_of_reprompting(self) -> None:
        source = (PROJECT_ROOT / "Pipeline" / "Setup-MediaPipeline" / "PathValidation.ps1").read_text(encoding="utf-8")

        self.assertIn("Keeping missing path for validation failure", source)
        self.assertIn("Keeping non-writable path for validation failure", source)
        self.assertIn("if ($script:UseAcceptDefaults)", source)

    def test_setup_wizard_guidance_uses_canonical_launchers(self) -> None:
        setup_root = PROJECT_ROOT / "Pipeline" / "Setup-MediaPipeline.ps1"
        user_interaction = PROJECT_ROOT / "Pipeline" / "Setup-MediaPipeline" / "UserInteraction.ps1"
        source = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                setup_root,
                user_interaction,
            )
        )

        self.assertIn("scripts\\dev\\setup.bat", source)
        self.assertIn("scripts\\dev\\run.bat", source)
        self.assertNotIn("Setup-MediaPipelineRemuxEncodeAIO.bat", source)
        self.assertNotIn("Run-MediaPipelineRemuxEncodeAIO.bat", source)

    def test_tauri_build_checker_uses_vs_dev_environment(self) -> None:
        source = (TAURI_ROOT / "Test-TauriShell-Build.ps1").read_text(encoding="utf-8")

        self.assertIn("Resolve-VsDevCmd", source)
        self.assertIn("npm run check", source)
        self.assertIn("Microsoft.VisualStudio.Component.VC.Tools.x86.x64", source)

    def test_tauri_build_checker_validates_webview_javascript_syntax(self) -> None:
        source = (TAURI_ROOT / "Test-TauriShell-Build.ps1").read_text(encoding="utf-8")

        self.assertIn("function Test-JavaScriptSyntax", source)
        self.assertIn("mediapipeline_desktop_app\\ui_web\\static", source)
        self.assertIn("Get-ChildItem -LiteralPath $assetRoot -Filter '*.js' -File", source)
        self.assertIn("& $NodePath --check $script.FullName", source)
        self.assertIn("JavaScript syntax check failed", source)
        self.assertIn("Test-JavaScriptSyntax -NodePath $node -StaticRoot $staticRoot", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)

    def test_tauri_build_checker_runs_rust_unit_tests(self) -> None:
        source = (TAURI_ROOT / "Test-TauriShell-Build.ps1").read_text(encoding="utf-8")

        self.assertIn("cargo test --manifest-path", source)
        self.assertIn("--lib", source)
        self.assertIn("& $cargo test --manifest-path $cargoToml --lib", source)
        self.assertIn("npm run check && cargo test", source)

    def test_tauri_bundle_config_uses_existing_windows_icon(self) -> None:
        config = json.loads((TAURI_ROOT / "src-tauri" / "tauri.conf.json").read_text(encoding="utf-8"))

        icons = config["bundle"]["icon"]
        self.assertIn("icons/launcher-logo.ico", icons)
        self.assertTrue((TAURI_ROOT / "src-tauri" / "icons" / "launcher-logo.ico").exists())

    def test_tauri_launch_checker_detects_window_and_backend_cleanup(self) -> None:
        source = (TAURI_ROOT / "Test-TauriShell-Launch.ps1").read_text(encoding="utf-8")

        self.assertIn("MediaPipelineRemuxEncodeAIO V6", source)
        self.assertIn("[ValidateSet('Auto', 'Dev', 'Packaged')]", source)
        self.assertIn("[string]$ExecutablePath", source)
        self.assertIn("function Resolve-PackagedTauriExecutable", source)
        self.assertIn("mediapipeline-tauri-shell.exe", source)
        self.assertIn("Launch mode: $launchMode", source)
        self.assertIn("No packaged Tauri executable was found", source)
        self.assertIn("mediapipeline_desktop_app\\.local_api_main", source)
        self.assertIn("function Get-TauriShellProcesses", source)
        self.assertIn("function Get-LogTail", source)
        self.assertIn("function Wait-ProcessIdsGone", source)
        self.assertIn("$baselineShellIds", source)
        self.assertIn("$newShellIds", source)
        self.assertIn("$baselineBackendIds", source)
        self.assertIn("CloseMainWindow", source)
        self.assertIn("Tauri window close request was not accepted", source)
        self.assertIn("Tauri shell process(es) still running after window close", source)
        self.assertIn("Backend process(es) still running", source)
        self.assertIn("stdout_tail=$(Get-LogTail -Path $stdoutLog)", source)
        self.assertIn("stderr_tail=$(Get-LogTail -Path $stderrLog)", source)
        self.assertIn("Stop-ProcessIdTree -ProcessId $shellPid", source)
        self.assertIn("Stop-ProcessIdTree -ProcessId $backendPid", source)
        self.assertIn("npm run dev", source)
        self.assertNotIn("src-tauri\\target\\release\\mediapipeline-tauri-shell.exe", source)

    def test_tauri_shell_prefers_bundle_relative_desktop_root_before_dev_manifest_root(self) -> None:
        source = _tauri_rust_source()

        self.assertIn("fn desktop_root_candidates_from_exe_dir", source)
        self.assertIn("packaged_desktop_root_candidates_cover_bundle_relative_locations", source)
        self.assertLess(
            source.index("let candidates = desktop_root_candidates_from_exe_dir(exe_dir);"),
            source.index("if dev_desktop_root.join(\"mediapipeline_desktop_app\").exists()"),
        )

    def test_tauri_preview_launcher_is_explicit_and_non_default(self) -> None:
        root_launcher = PROJECT_ROOT / "Start-MediaPipelineRemuxEncodeAIO-TauriPreview.bat"
        canonical_launcher = PROJECT_ROOT / "scripts" / "dev" / "start-tauri-preview.bat"
        shell_launcher = TAURI_ROOT / "Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1"
        readme = (TAURI_ROOT / "README.md").read_text(encoding="utf-8")
        canonical_text = canonical_launcher.read_text(encoding="utf-8")
        shell_text = shell_launcher.read_text(encoding="utf-8")

        self.assertFalse(root_launcher.exists())
        self.assertIn("Launch-MediaPipelineRemuxEncodeAIO-TauriPreview.ps1", canonical_text)
        self.assertIn("PowerShell-7.6.0-win-x64\\pwsh.exe", canonical_text)
        self.assertIn("V6 is the WebView-first workspace. V5 remains the external fallback if needed.", shell_text)
        self.assertIn("Tauri/WebView prerequisites are available.", shell_text)
        self.assertIn("Shell boundary: the WebView calls backend-owned local API commands", shell_text)
        self.assertIn("CheckOnly verifies tool/runtime layout and the local API module import only", shell_text)
        self.assertIn("Do not treat this shell as fully promoted", shell_text)
        self.assertIn("InstallNodePackages", shell_text)
        self.assertIn("CheckOnly", shell_text)
        self.assertIn("function Resolve-TauriPython", shell_text)
        self.assertIn("function Test-LocalApiBackendModule", shell_text)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", shell_text)
        self.assertIn("local_api_main --help", shell_text)
        self.assertIn("Backend  : $python", shell_text)
        self.assertIn("npm run dev", shell_text)
        self.assertIn("Resolve-VsDevCmd", shell_text)
        self.assertNotIn("Remove-Item", shell_text)
        self.assertIn("scripts\\dev\\start-tauri-preview.bat", readme)
        self.assertIn("Validation Ladder", readme)
        self.assertIn("Test-TauriShell-Build.ps1 -SkipLinkCheck", readme)
        self.assertIn("cargo test --manifest-path src-tauri\\Cargo.toml --lib", readme)
        self.assertIn("Test-WebViewRealMediaEvidenceSmoke.ps1", readme)
        self.assertIn("Test-WebViewCommandEvidenceSmoke.ps1", readme)
        self.assertIn("Test-WebViewRowDetailSmoke.ps1", readme)
        self.assertIn("Test-WebViewScheduleSmoke.ps1", readme)
        self.assertIn("Test-WebViewBrowserHighRiskSmoke.ps1", readme)
        self.assertIn("Test-WebViewBrowserScheduleSmoke.ps1", readme)
        self.assertIn("Test-WebViewBrowserLifecycleSmoke.ps1", readme)
        self.assertIn("Test-LocalApiMaintenanceDryRunContractSmoke.ps1", readme)
        self.assertIn("Test-LocalApiSampleValidationContractSmoke.ps1", readme)
        self.assertIn("Test-WebViewBrowserLargeTableSmoke.ps1", readme)
        self.assertIn("Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1", readme)
        self.assertIn("Test-WebViewBrowserPendingDrainGuardSmoke.ps1", readme)
        self.assertIn("Test-WebViewBrowserCompletedPendingProofSmoke.ps1", readme)
        self.assertIn("Test-WebViewBrowserMaintenanceReportsSmoke.ps1", readme)
        self.assertIn("Test-WebViewBrowserSampleValidationSmoke.ps1", readme)
        self.assertIn("Test-WebViewBrowserHomeLiveStateSmoke.ps1", readme)
        self.assertIn("Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1", readme)
        self.assertIn("Test-WebViewBrowserLayoutManagerSmoke.ps1", readme)
        self.assertIn("Test-WebViewSettingsLaunchPolicySmoke.ps1", readme)
        self.assertIn("Test-WebViewSettingsLaunchLiveConfigSmoke.ps1", readme)
        self.assertIn("Test-TauriShell-Launch.ps1 -TimeoutSeconds 180 -CloseTimeoutSeconds 30", readme)
        self.assertIn("PG-3 clean-machine validation", readme)
        self.assertIn("Test-TauriShell-Prereqs.ps1 -CheckOnly", readme)
        self.assertIn("Test-TauriShell-Launch.ps1 -Mode Packaged -TimeoutSeconds 180 -CloseTimeoutSeconds 30", readme)
        self.assertIn("scripts\\release\\build.ps1 -DestinationRoot C:\\Temp\\MediaPipelineRemuxEncodeAIO_V6_PG3 -IncludeTauriPreviewBinary", readme)
        self.assertIn("dev-mode `npm run dev` launch path", readme)
        self.assertIn("Passing the fixture, command-evidence, row-detail, schedule, browser schedule, browser backend lifecycle, local API Maintenance dry-run, local API sample validation, browser high-risk, browser diagnostics handoff, pending drain guard, completed pending proof, large-table, browser Maintenance/Reports, browser Sample Validation, browser Home live-state, browser Launch/Queue readiness, browser layout manager, settings/launch policy, live-config handoff, settings patch evidence, or preview launch smoke does not prove FFmpeg", readme)

    def test_api_browser_launcher_keeps_token_auth_enabled_by_default(self) -> None:
        root_launcher = PROJECT_ROOT / "Start-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.bat"
        canonical_launcher = PROJECT_ROOT / "scripts" / "dev" / "start-api-and-browser.bat"
        shell_launcher = PROJECT_ROOT / "DesktopApp" / "Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1"
        canonical_text = canonical_launcher.read_text(encoding="utf-8")
        shell_text = shell_launcher.read_text(encoding="utf-8")

        self.assertFalse(root_launcher.exists())
        self.assertIn("Launch-MediaPipelineRemuxEncodeAIO-ApiAndBrowser.ps1", canonical_text)
        self.assertIn("[switch]$NoTokenDevMode", shell_text)
        self.assertIn("Token auth: enabled (browser receives a per-run bootstrap token)", shell_text)
        self.assertIn("Token auth: DISABLED by explicit -NoTokenDevMode", shell_text)
        self.assertIn("if ($NoTokenDevMode)", shell_text)
        self.assertIn("$apiArgs += '--no-token'", shell_text)
        self.assertNotIn("'--no-token'\n)", shell_text)

    def test_webview_real_media_evidence_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewRealMediaEvidenceSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_real_media_smoke", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("publish, rename, save settings", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)

    def test_local_api_sample_validation_contract_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-LocalApiSampleValidationContractSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_sample_validation_api", source)
        self.assertIn("temporary token-protected local API", source)
        self.assertIn("/api/sample-validation/preview", source)
        self.assertIn("/api/sample-validation/append", source)
        self.assertIn("current-backend-evidence preview", source)
        self.assertIn("writes sample_validation_log.jsonl only inside temporary test state", source)
        self.assertIn("does not open a browser, process media", source)
        self.assertIn("does not accept outputs", source)
        self.assertIn("rewrite completed manifests", source)
        self.assertIn("probe FFmpeg/ffprobe", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)

    def test_webview_command_evidence_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewCommandEvidenceSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_command_evidence_smoke", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("evaluates backend-served WebView JavaScript with mocked DOM state", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("publish, rename, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)

    def test_webview_row_detail_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewRowDetailSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_row_detail_smoke", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("backend-served WebView JavaScript with mocked DOM selected-row state", source)
        self.assertIn("Queue, Completed, and Pending Publish row details", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("publish, rename, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)

    def test_webview_row_detail_smoke_covers_high_risk_selected_rows(self) -> None:
        source = (PROJECT_ROOT / "DesktopApp" / "tests" / "test_webview_row_detail_smoke.py").read_text(encoding="utf-8")

        self.assertIn('scenario="adversarial"', source)
        self.assertIn("tv_parse_unreliable", source)
        self.assertIn("Source changed during probe", source)
        self.assertIn("broken-output", source)
        self.assertIn("size_growth_over_5", source)
        self.assertIn("publish_missing_output", source)
        self.assertIn("unreadable_manifest", source)
        self.assertIn("do_not_drain", source)
        self.assertIn("manifest_repair", source)
        self.assertIn("does not process media", (PROJECT_ROOT / "SmokeTests" / "Test-WebViewRowDetailSmoke.ps1").read_text(encoding="utf-8"))

    def test_webview_schedule_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewScheduleSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_schedule_smoke", source)
        self.assertIn("evaluates WebView Schedule assets in Node with mocked DOM state", source)
        self.assertIn("Schedule Coverage Review", source)
        self.assertIn("selected day detail", source)
        self.assertIn("Schedule Editor preview/save routing", source)
        self.assertIn("app-state-write result copy", source)
        self.assertIn("write app state from frontend code", source)
        self.assertIn("start pipeline commands", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)

    def test_webview_browser_smokes_share_support_and_preserve_failure_detail(self) -> None:
        support_path = PROJECT_ROOT / "DesktopApp" / "tests" / "webview_browser_smoke_support.py"
        self.assertTrue(support_path.exists())
        support_source = support_path.read_text(encoding="utf-8")
        for fragment in (
            "def find_browser",
            "def free_port",
            "def bounded_text",
            "def assert_browser_smoke_process_ok",
            "def _is_transient_browser_runner_crash",
            "def run_node_browser_smoke",
            "except subprocess.TimeoutExpired",
            "_TRANSIENT_NATIVE_CRASH_RETURN_CODES",
            "_TRANSIENT_CDP_OPEN_STDERR_FRAGMENTS",
            "time.sleep(0.5)",
            "def browser_cdp_runner_prelude",
            "Return code:",
            "STDOUT:",
            "STDERR:",
            "function launchBrowser(args)",
            'stdio: ["ignore", "ignore", "ignore"]',
            "async function terminateBrowser(browser)",
            "function createCdpClient",
            "function httpJson",
            "waitForPageWebSocket",
            "Runtime.exceptionThrown",
        ):
            self.assertIn(fragment, support_source)

        browser_sources = sorted((PROJECT_ROOT / "DesktopApp" / "tests").glob("test_webview_browser_*.py"))
        self.assertGreaterEqual(len(browser_sources), 10)
        for path in browser_sources:
            source = path.read_text(encoding="utf-8")
            self.assertIn("webview_browser_smoke_support", source, path.name)
            self.assertIn("run_node_browser_smoke", source, path.name)
            self.assertIn("launchBrowser([", source, path.name)
            self.assertIn("await terminateBrowser(browser);", source, path.name)
            self.assertIn("browser_cdp_runner_prelude() + textwrap.dedent", source, path.name)
            self.assertNotIn("subprocess.run(", source, path.name)
            self.assertNotIn("from .test_webview_browser_high_risk_smoke import _find_browser", source, path.name)
            self.assertNotIn("from test_webview_browser_high_risk_smoke import _find_browser", source, path.name)
            self.assertNotIn('const fs = require("fs");', source, path.name)
            self.assertNotIn("function createCdpClient(wsUrl)", source, path.name)
            self.assertNotIn('stdio: ["ignore", "pipe", "pipe"]', source, path.name)
            self.assertNotIn("browser.once(\"exit\", resolve)", source, path.name)
            self.assertNotIn("throw new Error(result.exceptionDetails.text", source, path.name)
            self.assertNotIn("throw new Error(details.exception?.description || details.text", source, path.name)
            self.assertTrue("exception.value" in source or "exception?.value" in source, path.name)

    def test_webview_browser_high_risk_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewBrowserHighRiskSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_browser_high_risk_smoke", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("Chrome/Edge headless", source)
        self.assertIn("injected and backend-produced blocked Queue, broken Completed, and do-not-drain Pending Publish", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("publish, rename, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("skips cleanly when Chrome/Edge is not installed", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)

    def test_webview_browser_high_risk_smoke_uses_browser_without_new_package_dependency(self) -> None:
        source = (PROJECT_ROOT / "DesktopApp" / "tests" / "test_webview_browser_high_risk_smoke.py").read_text(encoding="utf-8")

        self.assertIn("remote-debugging-port", source)
        self.assertIn("WebSocket", source)
        self.assertIn("Chrome or Edge is required", source)
        self.assertIn("_write_high_risk_fixture_state", source)
        self.assertIn("backendProducedHighRiskScript", source)
        self.assertIn("test_real_browser_renders_backend_produced_high_risk_rows", source)
        self.assertIn('"mutateRows": mutate_rows', source)
        self.assertIn("tv_parse_unreliable", source)
        self.assertIn("broken-output", source)
        self.assertIn("do_not_drain", source)
        self.assertIn("manifest_repair", source)
        self.assertNotIn("playwright", source.casefold())
        self.assertNotIn("puppeteer", source.casefold())
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_webview_browser_diagnostics_handoff_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewBrowserDiagnosticsHandoffSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_browser_diagnostics_handoff_smoke", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("Chrome/Edge headless", source)
        self.assertIn("actual Queue, Completed, and Pending Publish table rows before exercising read-only diagnostics bridge, tail, and allowlisted open controls", source)
        self.assertIn("selected-row investigation signals, current-filter visibility, clear-filter buttons, and text/status/investigation guardrails before launch, rerun, cleanup, or publish decisions", source)
        self.assertIn("bounded backend tail output and diagnostics.open command-result feedback", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("publish, rename, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("skips cleanly when Chrome/Edge is not installed", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)

    def test_webview_browser_diagnostics_handoff_smoke_uses_browser_without_mutation_routes(self) -> None:
        source = (PROJECT_ROOT / "DesktopApp" / "tests" / "test_webview_browser_diagnostics_handoff_smoke.py").read_text(encoding="utf-8")

        self.assertIn("remote-debugging-port", source)
        self.assertIn("WebSocket", source)
        self.assertIn("Chrome or Edge is required", source)
        self.assertIn("_write_high_risk_fixture_state", source)
        self.assertIn("test_real_browser_clicks_read_only_diagnostics_handoffs_for_backend_risk_rows", source)
        self.assertIn("test_real_browser_clicks_table_rows_before_read_only_diagnostics_handoffs", source)
        self.assertIn("tableClickRows", source)
        self.assertIn("#queue-rows tr[data-row-key]", source)
        self.assertIn("#completed-history-rows tr[data-row-key]", source)
        self.assertIn("#pending-rows tr[data-row-key]", source)
        self.assertIn("queue-filter-summary", source)
        self.assertIn("completed-filter-summary", source)
        self.assertIn("pending-filter-summary", source)
        self.assertIn("queue-status-filter", source)
        self.assertIn("completed-history-status-filter", source)
        self.assertIn("pending-status-filter", source)
        self.assertIn("queue-investigation-filter", source)
        self.assertIn("completed-history-investigation-filter", source)
        self.assertIn("pending-investigation-filter", source)
        self.assertIn("queue-clear-filters-button", source)
        self.assertIn("completed-history-clear-filters-button", source)
        self.assertIn("pending-clear-filters-button", source)
        self.assertIn("Selected row visible in table: no", source)
        self.assertIn("Selected row visible in table: yes", source)
        self.assertIn("status=ready/healthy", source)
        self.assertIn("view=priority rows", source)
        self.assertIn("view=route review", source)
        self.assertIn("view=ready to drain", source)
        self.assertIn("Hidden review rows: 1.", source)
        self.assertIn("requestDiagnosticsTail", source)
        self.assertIn("requestDiagnosticsOpen", source)
        self.assertIn("historyHasTarget", source)
        self.assertIn("queue_snapshot", source)
        self.assertIn("completed_manifest", source)
        self.assertIn("pending_publish", source)
        self.assertNotIn("playwright", source.casefold())
        self.assertNotIn("puppeteer", source.casefold())
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_webview_browser_pending_drain_guard_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewBrowserPendingDrainGuardSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_browser_pending_drain_guard_smoke", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("Chrome/Edge headless", source)
        self.assertIn("Publish Button Guard refreshes immediately", source)
        self.assertIn("frontend_guard evidence without posting /api/pipeline/start", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("drain pending publish", source)
        self.assertIn("rename, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("skips cleanly when Chrome/Edge is not installed", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)

    def test_webview_browser_pending_drain_guard_smoke_blocks_pipeline_post(self) -> None:
        source = (PROJECT_ROOT / "DesktopApp" / "tests" / "test_webview_browser_pending_drain_guard_smoke.py").read_text(encoding="utf-8")

        self.assertIn("remote-debugging-port", source)
        self.assertIn("WebSocket", source)
        self.assertIn("Chrome or Edge is required", source)
        self.assertIn("test_real_browser_refreshes_guard_after_blocked_recovery_plan_and_blocks_drain_post", source)
        self.assertIn("renderPendingRecoveryPlanResult", source)
        self.assertIn("startPendingPublishDrain", source)
        self.assertIn("pendingDrainGuardState", source)
        self.assertIn("frontend_guard", source)
        self.assertIn("blocked drain attempted /api/pipeline/start", source)
        self.assertIn("confirmCalls", source)
        self.assertIn("Decision: Do not drain", source)
        self.assertNotIn("playwright", source.casefold())
        self.assertNotIn("puppeteer", source.casefold())
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_webview_browser_completed_pending_proof_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewBrowserCompletedPendingProofSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_browser_completed_pending_proof_smoke", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("Chrome/Edge headless", source)
        self.assertIn("Completed/Pending proof board", source)
        self.assertIn("Sample Validation handoff", source)
        self.assertIn("exact completed-output to pending-destination overlap", source)
        self.assertIn("missing-output-without-proof detail", source)
        self.assertIn("selected Pending row Completed Manifest correlation remains read-only", source)
        self.assertIn("same-leaf proof wording remains a duplicate-title hint", source)
        self.assertIn("does not append validation records", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("drain pending publish", source)
        self.assertIn("rename, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("skips cleanly when Chrome/Edge is not installed", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)

    def test_webview_browser_completed_pending_proof_smoke_uses_browser_without_mutation_routes(self) -> None:
        source = (PROJECT_ROOT / "DesktopApp" / "tests" / "test_webview_browser_completed_pending_proof_smoke.py").read_text(encoding="utf-8")

        self.assertIn("remote-debugging-port", source)
        self.assertIn("WebSocket", source)
        self.assertIn("Chrome or Edge is required", source)
        self.assertIn("test_real_browser_renders_completed_pending_proof_overlap_and_missing_output_detail", source)
        self.assertIn("completed-pending-proof-detail", source)
        self.assertIn("completedPendingProofDetailLines", source)
        self.assertIn("publish-reconciliation-detail", source)
        self.assertIn("requestPublishReconciliation", source)
        self.assertIn("Backend publish reconciliation row:", source)
        self.assertIn("Mutation guardrail: this backend row", source)
        self.assertIn("pendingSelectedCompletedCorrelationLines", source)
        self.assertIn("pendingSampleValidationHandoffLines", source)
        self.assertIn("Completed Manifest correlation for selected pending row", source)
        self.assertIn("Pending destination overlap", source)
        self.assertIn("Missing output without pending proof", source)
        self.assertIn("same-leaf matches are duplicate-title hints only", source)
        self.assertIn("postCount", source)
        self.assertNotIn("playwright", source.casefold())
        self.assertNotIn("puppeteer", source.casefold())
        # Mutation routes must appear only in an explicit forbidden-route guard list, never as direct apiPost calls.
        self.assertIn("forbiddenPosts", source)
        self.assertIn("posted forbidden routes", source)
        self.assertIn("/api/rename/apply", source)  # present in forbidden-list guard, not as a call
        self.assertIn("/api/settings/save-patch", source)
        self.assertIn("/api/pending-publish/drain", source)
        self.assertIn("/api/pipeline/start", source)

    def test_webview_browser_large_table_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewBrowserLargeTableSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_browser_large_table_smoke", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("Chrome/Edge headless", source)
        self.assertIn("260-row payloads disclose the 250-row render cap", source)
        self.assertIn("filter warnings", source)
        self.assertIn("hidden selected-row detail", source)
        self.assertIn("no backend mutation routes are posted", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("drain pending publish", source)
        self.assertIn("rerun, rename, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("skips cleanly when Chrome/Edge is not installed", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)

    def test_webview_browser_large_table_smoke_uses_browser_without_mutation_posts(self) -> None:
        source = (PROJECT_ROOT / "DesktopApp" / "tests" / "test_webview_browser_large_table_smoke.py").read_text(encoding="utf-8")

        self.assertIn("remote-debugging-port", source)
        self.assertIn("WebSocket", source)
        self.assertIn("Chrome or Edge is required", source)
        self.assertIn("test_real_browser_discloses_large_daily_table_caps_without_mutation_posts", source)
        self.assertIn("250 shown / 260 filtered / 260 rows", source)
        self.assertIn("Display cap: only the first 250 filtered rows are rendered", source)
        self.assertIn("Hidden review rows: 1", source)
        self.assertIn("Selected row visible in table: no", source)
        self.assertIn("#queue-rows tr[data-row-key]", source)
        self.assertIn("#completed-rows tr[data-row-key]", source)
        self.assertIn("#pending-rows tr[data-row-key]", source)
        self.assertIn("large-table smoke posted mutation routes", source)
        self.assertIn("/api/pipeline/start", source)
        self.assertIn("/api/rerun/start", source)
        self.assertIn("/api/pending-publish/recovery-plan", source)
        self.assertIn("/api/rename/apply", source)
        self.assertIn("/api/settings/save-patch", source)
        self.assertNotIn("playwright", source.casefold())
        self.assertNotIn("puppeteer", source.casefold())

    def test_webview_browser_rename_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewBrowserRenameSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_browser_rename_smoke", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("Chrome/Edge headless", source)
        self.assertIn("actual Rename preview rows and Check Applicable Rows", source)
        self.assertIn("Pipeline Handoff", source)
        self.assertIn("large-preview render cap", source)
        self.assertIn("duplicate-target blocking", source)
        self.assertIn("does not call rename.apply", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("skips cleanly when Chrome/Edge is not installed", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)

    def test_webview_browser_rename_smoke_uses_browser_without_backend_mutation(self) -> None:
        source = (PROJECT_ROOT / "DesktopApp" / "tests" / "test_webview_browser_rename_smoke.py").read_text(encoding="utf-8")

        self.assertIn("remote-debugging-port", source)
        self.assertIn("WebSocket", source)
        self.assertIn("Chrome or Edge is required", source)
        self.assertIn("test_real_browser_renders_rename_readiness_and_blocks_duplicate_apply", source)
        self.assertIn("rename-apply-readiness-rows", source)
        self.assertIn("rename-pipeline-handoff", source)
        self.assertIn("largeRows", source)
        self.assertIn("Render cap visibility", source)
        self.assertIn("rename-check-applicable-button", source)
        self.assertIn("rename-apply-button", source)
        self.assertIn("blocked by apply readiness", source)
        self.assertIn("duplicate destination target", source)
        self.assertIn("posted", source)
        self.assertNotIn("playwright", source.casefold())
        self.assertNotIn("puppeteer", source.casefold())
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_webview_browser_network_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewBrowserNetworkSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_browser_network_smoke", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("Chrome/Edge headless", source)
        self.assertIn("read-only network runtime/lifecycle readiness", source)
        self.assertIn("lifecycle handoff", source)
        self.assertIn("persisted worker rows", source)
        self.assertIn("filters warn when active/problem worker rows are hidden", source)
        self.assertIn("no network lifecycle mutation commands are posted", source)
        self.assertIn("Worker Mode Settings save is not exercised by this smoke", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("publish, rename, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("start or stop coordinator/workers", source)
        self.assertIn("skips cleanly when Chrome/Edge is not installed", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)

    def test_webview_browser_network_smoke_uses_browser_without_lifecycle_mutation(self) -> None:
        source = (PROJECT_ROOT / "DesktopApp" / "tests" / "test_webview_browser_network_smoke.py").read_text(encoding="utf-8")

        self.assertIn("remote-debugging-port", source)
        self.assertIn("WebSocket", source)
        self.assertIn("Chrome or Edge is required", source)
        self.assertIn("test_real_browser_network_worker_filters_warn_when_hiding_review_rows", source)
        self.assertIn("network-worker-filter-summary", source)
        self.assertIn("network-lifecycle-summary", source)
        self.assertIn("renderNetworkLifecycleHandoff", source)
        self.assertIn("network-worker-status-filter", source)
        self.assertIn("No active/problem worker rows are hidden", source)
        self.assertIn("active/problem worker rows are hidden", source)
        self.assertIn("Lifecycle controls remain backend-owned", source)
        self.assertIn("Mutation guardrail", source)
        self.assertIn("/api/network/workers", source)
        self.assertIn("/api/diagnostics/open", source)
        self.assertNotIn("playwright", source.casefold())
        self.assertNotIn("puppeteer", source.casefold())
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)
        self.assertNotIn("/api/pipeline/start", source)

    def test_webview_browser_telemetry_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewBrowserTelemetrySmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_browser_telemetry_smoke", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("Chrome/Edge headless", source)
        self.assertIn("Live telemetry rendering", source)
        self.assertIn("zero-percent NVENC remains visible without duplicate idle wording", source)
        self.assertIn("top-level GPU telemetry is present", source)
        self.assertIn("CPU/RAM-only fallback", source)
        self.assertIn("does not collect live GPU telemetry", source)
        self.assertIn("process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("skips cleanly when Chrome/Edge is not installed", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)

    def test_webview_browser_telemetry_smoke_uses_browser_without_media_mutation(self) -> None:
        source = (PROJECT_ROOT / "DesktopApp" / "tests" / "test_webview_browser_telemetry_smoke.py").read_text(encoding="utf-8")

        self.assertIn("remote-debugging-port", source)
        self.assertIn("WebSocket", source)
        self.assertIn("Chrome or Edge is required", source)
        self.assertIn("test_real_browser_keeps_zero_percent_nvenc_visible", source)
        self.assertIn("telemetryVisibleGpuRows", source)
        self.assertIn("NVENC present.", source)
        self.assertIn("redundant idle wording", source)
        self.assertIn("top-level zero-percent GPU telemetry did not synthesize a visible GPU row", source)
        self.assertIn("CPU/RAM only", source)
        self.assertNotIn("playwright", source.casefold())
        self.assertNotIn("puppeteer", source.casefold())
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)
        self.assertNotIn("/api/pipeline/start", source)

    def test_webview_rename_readiness_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewRenameReadinessSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_rename_readiness_smoke", source)
        self.assertIn("Apply Readiness", source)
        self.assertIn("Pipeline Handoff", source)
        self.assertIn("large-preview render cap", source)
        self.assertIn("duplicate-target", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("publish, rename files, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_webview_browser_settings_launch_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewBrowserSettingsLaunchSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_browser_settings_launch_smoke", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("Chrome/Edge headless", source)
        self.assertIn("staged settings patch", source)
        self.assertIn("Settings-to-Launch", source)
        self.assertIn("cancelled Save Patch remains visible", source)
        self.assertIn("does not save settings", source)
        self.assertIn("process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("skips cleanly when Chrome/Edge is not installed", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_webview_browser_schedule_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewBrowserScheduleSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_browser_schedule_smoke", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("Chrome/Edge headless", source)
        self.assertIn("Schedule Editor preview/save routing", source)
        self.assertIn("confirmed backend app-state write", source)
        self.assertIn("refreshed Launch timing trust", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("publish, rename files, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("skips cleanly when Chrome/Edge is not installed", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_webview_browser_lifecycle_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewBrowserLifecycleSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_browser_lifecycle_smoke", source)
        self.assertIn("temporary local API instances against generated temporary state", source)
        self.assertIn("Chrome/Edge headless", source)
        self.assertIn("backend lifecycle controls", source)
        self.assertIn("continuous schedule-stop watcher is armed", source)
        self.assertIn("backend-owned /api/backend/shutdown after confirmation", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("publish, rename files, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("skips cleanly when Chrome/Edge is not installed", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_webview_browser_maintenance_reports_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewBrowserMaintenanceReportsSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_browser_maintenance_reports_smoke", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("Chrome/Edge headless", source)
        self.assertIn("Maintenance and Reports pages", source)
        self.assertIn("Maintenance health, dry-run result rendering, dry-run history, Reports failure/audit triage", source)
        self.assertIn("failure-marker clear is dry-run preview only", source)
        self.assertIn("no non-dry-run backend mutation routes are posted", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("run audit, run CSV rerun", source)
        self.assertIn("rename, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("skips cleanly when Chrome/Edge is not installed", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_webview_browser_sample_validation_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewBrowserSampleValidationSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_browser_sample_validation_smoke", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("Chrome/Edge headless", source)
        self.assertIn("Home Sample Validation controls", source)
        self.assertIn("permits only /api/sample-validation/preview", source)
        self.assertIn("no append or mutation routes are posted", source)
        self.assertIn("does not append validation records", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("run audit, run CSV rerun", source)
        self.assertIn("rename, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("skips cleanly when Chrome/Edge is not installed", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_webview_browser_home_live_state_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewBrowserHomeLiveStateSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_browser_home_live_state_smoke", source)
        self.assertIn("temporary local API against generated temporary state and a generated command journal", source)
        self.assertIn("Chrome/Edge headless", source)
        self.assertIn("Daily-Driver Checklist", source)
        self.assertIn("Operator Readiness", source)
        self.assertIn("Active Work", source)
        self.assertIn("Command Results", source)
        self.assertIn("Sample Validation posture", source)
        self.assertIn("Real-Media Validation Worksheet handoff", source)
        self.assertIn("no POST routes are sent", source)
        self.assertIn("does not append validation records", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("run audit, run CSV rerun", source)
        self.assertIn("rename, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("skips cleanly when Chrome/Edge is not installed", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_webview_browser_launch_queue_readiness_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewBrowserLaunchQueueReadinessSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_browser_launch_queue_readiness_smoke", source)
        self.assertIn("temporary local API against generated temporary state, a generated launch command journal, and a temporary sample-validation record", source)
        self.assertIn("Chrome/Edge headless", source)
        self.assertIn("Launch preflight", source)
        self.assertIn("Queue launch decision", source)
        self.assertIn("Schedule guidance", source)
        self.assertIn("close-readiness", source)
        self.assertIn("launch command-review evidence", source)
        self.assertIn("Sample Validation record evidence", source)
        self.assertIn("Pilot category coverage", source)
        self.assertIn("no POST routes are sent", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("run audit, run CSV rerun", source)
        self.assertIn("drain pending publish", source)
        self.assertIn("rename, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("skips cleanly when Chrome/Edge is not installed", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_webview_browser_layout_manager_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewBrowserLayoutManagerSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_webview_browser_layout_manager_smoke", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("Chrome/Edge headless", source)
        self.assertIn("real backend-served Layout Editor drawer", source)
        self.assertIn("Queue, Completed, Settings, Diagnostics, Launch, and Reports", source)
        self.assertIn("listed in the drawer", source)
        self.assertIn("inactive Settings-family subtabs stay hidden", source)
        self.assertIn("no backend mutation routes are posted", source)
        self.assertIn("media/sidecar/manifest fixture artifacts stay unchanged", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("run audit, run CSV rerun", source)
        self.assertIn("drain pending publish", source)
        self.assertIn("rename, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("skips cleanly when Chrome/Edge is not installed", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_local_api_lifecycle_contract_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-LocalApiLifecycleContractSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_local_api_lifecycle_contract_smoke", source)
        self.assertIn("temporary token-protected local API instances against generated temporary state", source)
        self.assertIn("/api/backend/close-readiness safe and continuous schedule-stop watcher blocked payloads", source)
        self.assertIn("/api/backend/shutdown token enforcement, safe info result, and watcher-blocked failure result", source)
        self.assertIn("direct backend shutdown POST is exercised only against temporary test backends", source)
        self.assertIn("does not open a browser", source)
        self.assertIn("does not open a browser, process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("publish, rename files, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_local_api_maintenance_dry_run_contract_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-LocalApiMaintenanceDryRunContractSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("DesktopApp.tests.test_local_api_maintenance_dry_run_contract_smoke", source)
        self.assertIn("temporary token-protected local API against generated temporary state", source)
        self.assertIn("/api/maintenance/release-dry-run", source)
        self.assertIn("/api/maintenance/completed-backfill-dry-run", source)
        self.assertIn("release dry-run no-manifest/no-zip evidence", source)
        self.assertIn("completed-manifest backfill dry-run no-manifest-write evidence", source)
        self.assertIn("command journal and RunLogs evidence are written only inside temporary test state", source)
        self.assertIn("does not open a browser", source)
        self.assertIn("does not open a browser, process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("run audit, run CSV rerun", source)
        self.assertIn("publish, rename files, save settings", source)
        self.assertIn("mutate queue state", source)
        self.assertIn("drain pending publish", source)
        self.assertIn("does not create a release package", source)
        self.assertIn("write a release manifest", source)
        self.assertIn("rewrite completed manifests", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_webview_settings_launch_policy_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewSettingsLaunchPolicySmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("test_backend_served_webview_fixture_has_settings_launch_policy_handoff", source)
        self.assertIn("temporary local API against generated temporary state", source)
        self.assertIn("validates read-only Settings and Launch policy handoff visibility", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("publish, rename, save settings", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("MediaPipeline.ps1", source)
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_webview_settings_launch_live_config_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewSettingsLaunchLiveConfigSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("mediapipeline_desktop_app.webview_settings_live_smoke", source)
        self.assertIn("current saved config", source)
        self.assertIn("validates read-only Settings and Launch policy handoff visibility against live config data", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("publish, rename, save settings", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertIn("$env:PYTHONPATH = $desktopAppRoot", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/settings/save-patch", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_webview_settings_patch_evidence_smoke_script_is_bounded(self) -> None:
        script = PROJECT_ROOT / "SmokeTests" / "Test-WebViewSettingsPatchEvidenceSmoke.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("mediapipeline_desktop_app.webview_settings_patch_smoke", source)
        self.assertIn("generated temporary config", source)
        self.assertIn("Preview Patch, denied Save Patch, confirmed Save Patch", source)
        self.assertIn("does not use the current saved config", source)
        self.assertIn("does not process media", source)
        self.assertIn("launch pipeline commands", source)
        self.assertIn("publish, rename, mutate queue state", source)
        self.assertIn("DesktopApp\\Runtime\\Python\\python.exe", source)
        self.assertIn("Pipeline\\Runtime\\Python\\python.exe", source)
        self.assertIn("$env:PYTHONDONTWRITEBYTECODE = '1'", source)
        self.assertIn("$env:PYTHONPATH = $desktopAppRoot", source)
        self.assertNotIn("Remove-Item", source)
        self.assertNotIn("Start-Process", source)
        self.assertNotIn("/api/rename/apply", source)
        self.assertNotIn("/api/pending-publish/drain", source)

    def test_browser_backed_smokes_use_shared_process_lifecycle_helpers(self) -> None:
        support = (PROJECT_ROOT / "DesktopApp" / "tests" / "webview_browser_smoke_support.py").read_text(
            encoding="utf-8"
        )
        self.assertIn("def run_node_browser_smoke", support)
        self.assertIn("except subprocess.TimeoutExpired", support)
        self.assertIn("def _is_transient_browser_runner_crash", support)
        self.assertIn("_TRANSIENT_NATIVE_CRASH_RETURN_CODES", support)
        self.assertIn("_TRANSIENT_CDP_OPEN_STDERR_FRAGMENTS", support)
        self.assertIn("CDP websocket error while opening", support)
        self.assertIn("time.sleep(0.5)", support)
        self.assertIn("function launchBrowser(args)", support)
        self.assertIn('stdio: ["ignore", "ignore", "ignore"]', support)
        self.assertIn("async function terminateBrowser(browser)", support)
        self.assertIn("browser.exitCode !== null || browser.signalCode !== null", support)
        self.assertIn("Timed out after {timeout_seconds}s.", support)

        browser_smokes = sorted((PROJECT_ROOT / "DesktopApp" / "tests").glob("test_webview_browser_*_smoke.py"))
        self.assertGreaterEqual(len(browser_smokes), 10)
        for path in browser_smokes:
            source = path.read_text(encoding="utf-8")
            self.assertIn("run_node_browser_smoke", source, path.name)
            self.assertIn("launchBrowser([", source, path.name)
            self.assertIn("await terminateBrowser(browser);", source, path.name)
            self.assertNotIn("subprocess.run(", source, path.name)
            self.assertNotIn('stdio: ["ignore", "pipe", "pipe"]', source, path.name)
            self.assertNotIn("browser.once(\"exit\", resolve)", source, path.name)
            self.assertNotIn("const browser = spawn(payload.browserPath", source, path.name)

    def test_tauri_pg_harnesses_use_debug_auth_capture_not_public_index_token(self) -> None:
        source = _tauri_rust_source()
        self.assertIn("MEDIA_PIPELINE_TAURI_TEST_TOKEN_CAPTURE_FILE", source)
        self.assertIn("mediapipeline_tauri_test_auth_capture.v1", source)
        self.assertIn("maybe_write_debug_backend_auth_capture", source)
        self.assertIn(".backend_auth.json", source)
        self.assertIn("system temp directory", source)

        for script_name in (
            "Test-TauriShell-PG1ActiveClose.ps1",
            "Test-TauriShell-PG2WebViewLaunch.ps1",
            "Test-TauriShell-PG2SampleValidationAppend.ps1",
        ):
            script = TAURI_ROOT / script_name
            self.assertTrue(script.exists(), script_name)
            text = script.read_text(encoding="utf-8")
            self.assertIn("MEDIA_PIPELINE_TAURI_TEST_TOKEN_CAPTURE_FILE", text)
            self.assertIn("Wait-BackendTokenCapture", text)
            self.assertIn("Object\\.assign", text)
            self.assertIn("Backend WebView bootstrap leaked the bearer token in Tauri mode.", text)
            self.assertNotIn("Backend bootstrap did not expose a bearer token", text)

    def test_tauri_pg2_webview_launch_harness_uses_webview_start_not_backend_direct_post(self) -> None:
        script = TAURI_ROOT / "Test-TauriShell-PG2WebViewLaunch.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("MEDIA_PIPELINE_TAURI_TEST_AUTOMATION", source)
        self.assertIn("pg2-webview-launch", source)
        self.assertIn("MEDIA_PIPELINE_TAURI_TEST_AUTOLAUNCH_SINGLE_FILE", source)
        self.assertIn("shellSurface", source)
        self.assertIn("Wait-ActiveJobForSource", source)
        self.assertIn("/api/commands?limit=15", source)
        self.assertIn("/api/completed?limit=30", source)
        self.assertNotIn("/api/pipeline/start", source)
        self.assertNotIn("/api/sample-validation/append", source)

    def test_tauri_webview_uia_probe_does_not_launch_media(self) -> None:
        script = TAURI_ROOT / "Test-TauriShell-WebViewUiAutomationProbe.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("Get-UiAutomationRows", source)
        self.assertIn("UIAutomationClient", source)
        self.assertIn("AutomationElement", source)
        self.assertNotIn("/api/pipeline/start", source)
        self.assertNotIn("MEDIA_PIPELINE_TAURI_TEST_AUTOLAUNCH_SINGLE_FILE", source)

    def test_tauri_pg2_sample_validation_append_harness_uses_webview_append(self) -> None:
        script = TAURI_ROOT / "Test-TauriShell-PG2SampleValidationAppend.ps1"
        self.assertTrue(script.exists())
        source = script.read_text(encoding="utf-8")

        self.assertIn("pg2-sample-validation-append", source)
        self.assertIn("Wait-SampleValidationRecord", source)
        self.assertIn("sample_validation_record_id", source)
        self.assertIn("shellSurface", source)
        self.assertNotIn("/api/sample-validation/append", source)
        self.assertNotIn("/api/pipeline/start", source)


if __name__ == "__main__":
    unittest.main()

