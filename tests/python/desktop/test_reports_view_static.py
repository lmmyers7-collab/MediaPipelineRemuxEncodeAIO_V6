from __future__ import annotations

import shutil
import subprocess
import textwrap
import unittest
from pathlib import Path

from mediapipeline.tools.paths import find_repo_root
from tests.css_import_resolver import resolve_css_imports


REPO_ROOT = find_repo_root(Path(__file__))
REPORTS_VIEW = (
    REPO_ROOT
    / "apps"
    / "desktop"
    / "webview"
    / "static"
    / "assets"
    / "reportsView.js"
)
REPORTS_STATE = (
    REPO_ROOT
    / "apps"
    / "desktop"
    / "webview"
    / "static"
    / "assets"
    / "reports"
    / "state.js"
)
REPORTS_SHARED = (
    REPO_ROOT
    / "apps"
    / "desktop"
    / "webview"
    / "static"
    / "assets"
    / "reports"
    / "shared.js"
)
REPORTS_SHELL = (
    REPO_ROOT
    / "apps"
    / "desktop"
    / "webview"
    / "static"
    / "assets"
    / "reports"
    / "shell.js"
)
REPORTS_FAILURE_MODEL = (
    REPO_ROOT
    / "apps"
    / "desktop"
    / "webview"
    / "static"
    / "assets"
    / "reports"
    / "failureModel.js"
)
REPORTS_FAILURE_COMMANDS = (
    REPO_ROOT
    / "apps"
    / "desktop"
    / "webview"
    / "static"
    / "assets"
    / "reports"
    / "failureCommands.js"
)
REPORTS_FAILURE_VIEW = (
    REPO_ROOT
    / "apps"
    / "desktop"
    / "webview"
    / "static"
    / "assets"
    / "reports"
    / "failureView.js"
)
REPORTS_AUDIT_MODEL = (
    REPO_ROOT
    / "apps"
    / "desktop"
    / "webview"
    / "static"
    / "assets"
    / "reports"
    / "auditModel.js"
)
REPORTS_AUDIT_VIEW = (
    REPO_ROOT
    / "apps"
    / "desktop"
    / "webview"
    / "static"
    / "assets"
    / "reports"
    / "auditView.js"
)
REPORTS_AUDIT_COMMANDS = (
    REPO_ROOT
    / "apps"
    / "desktop"
    / "webview"
    / "static"
    / "assets"
    / "reports"
    / "auditCommands.js"
)
REPORTS_TRIAGE = (
    REPO_ROOT
    / "apps"
    / "desktop"
    / "webview"
    / "static"
    / "assets"
    / "reports"
    / "triage.js"
)
APP_JS = REPO_ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "app.js"
OPERATOR_TOAST = REPO_ROOT / "apps" / "desktop" / "webview" / "static" / "assets" / "operatorToast.js"
INDEX_HTML = REPO_ROOT / "apps" / "desktop" / "webview" / "static" / "index.html"
REPORTS_PAGE = (
    REPO_ROOT
    / "apps"
    / "desktop"
    / "webview"
    / "static"
    / "partials"
    / "page-reports.html"
)
COMPONENT_STYLES = (
    REPO_ROOT
    / "apps"
    / "desktop"
    / "webview"
    / "static"
    / "assets"
    / "styles.components.css"
)


def _read_component_styles() -> str:
    return resolve_css_imports(COMPONENT_STYLES, COMPONENT_STYLES.parent)


class ReportsViewStaticTests(unittest.TestCase):
    def test_reports_split_children_load_before_parent_and_are_private(self) -> None:
        html = INDEX_HTML.read_text(encoding="utf-8")
        source = REPORTS_VIEW.read_text(encoding="utf-8")
        state_source = REPORTS_STATE.read_text(encoding="utf-8")
        shared_source = REPORTS_SHARED.read_text(encoding="utf-8")
        shell_source = REPORTS_SHELL.read_text(encoding="utf-8")
        failure_model_source = REPORTS_FAILURE_MODEL.read_text(encoding="utf-8")
        failure_commands_source = REPORTS_FAILURE_COMMANDS.read_text(encoding="utf-8")
        failure_view_source = REPORTS_FAILURE_VIEW.read_text(encoding="utf-8")
        audit_model_source = REPORTS_AUDIT_MODEL.read_text(encoding="utf-8")
        audit_view_source = REPORTS_AUDIT_VIEW.read_text(encoding="utf-8")
        audit_commands_source = REPORTS_AUDIT_COMMANDS.read_text(encoding="utf-8")
        triage_source = REPORTS_TRIAGE.read_text(encoding="utf-8")

        self.assertLess(html.index("/assets/reports/state.js"), html.index("/assets/reportsView.js"))
        self.assertLess(html.index("/assets/reports/shared.js"), html.index("/assets/reportsView.js"))
        self.assertLess(html.index("/assets/reports/shell.js"), html.index("/assets/reportsView.js"))
        self.assertLess(html.index("/assets/reports/failureModel.js"), html.index("/assets/reportsView.js"))
        self.assertLess(html.index("/assets/reports/failureCommands.js"), html.index("/assets/reportsView.js"))
        self.assertLess(html.index("/assets/reports/failureCommands.js"), html.index("/assets/reports/failureView.js"))
        self.assertLess(html.index("/assets/reports/failureView.js"), html.index("/assets/reportsView.js"))
        self.assertLess(html.index("/assets/reports/auditModel.js"), html.index("/assets/reportsView.js"))
        self.assertLess(html.index("/assets/reports/auditView.js"), html.index("/assets/reportsView.js"))
        self.assertLess(html.index("/assets/reports/auditCommands.js"), html.index("/assets/reportsView.js"))
        self.assertLess(html.index("/assets/reports/auditView.js"), html.index("/assets/reports/auditCommands.js"))
        self.assertLess(html.index("/assets/reports/triage.js"), html.index("/assets/reportsView.js"))
        self.assertLess(html.index("/assets/reports/auditCommands.js"), html.index("/assets/reports/triage.js"))
        self.assertIn("window.__reportsViewStateModule", state_source)
        self.assertIn("window.__reportsViewSharedModule", shared_source)
        self.assertIn("window.__reportsViewShellModule", shell_source)
        self.assertIn("window.__reportsViewFailureModelModule", failure_model_source)
        self.assertIn("window.__reportsViewFailureCommandsModule", failure_commands_source)
        self.assertIn("window.__reportsViewFailureViewModule", failure_view_source)
        self.assertIn("window.__reportsViewAuditModelModule", audit_model_source)
        self.assertIn("window.__reportsViewAuditViewModule", audit_view_source)
        self.assertIn("window.__reportsViewAuditCommandsModule", audit_commands_source)
        self.assertIn("window.__reportsViewTriageModule", triage_source)
        self.assertIn("delete window.__reportsViewStateModule;", source)
        self.assertIn("delete window.__reportsViewSharedModule;", source)
        self.assertIn("delete window.__reportsViewShellModule;", source)
        self.assertIn("delete window.__reportsViewFailureModelModule;", source)
        self.assertIn("delete window.__reportsViewFailureCommandsModule;", source)
        self.assertIn("delete window.__reportsViewFailureViewModule;", source)
        self.assertIn("delete window.__reportsViewAuditModelModule;", source)
        self.assertIn("delete window.__reportsViewAuditViewModule;", source)
        self.assertIn("delete window.__reportsViewAuditCommandsModule;", source)
        self.assertIn("delete window.__reportsViewTriageModule;", source)
        self.assertIn('throw new Error("reports/state.js must load before reportsView.js")', source)
        self.assertIn('throw new Error("reports/shared.js must load before reportsView.js")', source)
        self.assertIn('throw new Error("reports/shell.js must load before reportsView.js")', source)
        self.assertIn('throw new Error("reports/failureModel.js must load before reportsView.js")', source)
        self.assertIn('throw new Error("reports/failureCommands.js must load before reportsView.js")', source)
        self.assertIn('throw new Error("reports/failureView.js must load before reportsView.js")', source)
        self.assertIn('throw new Error("reports/auditModel.js must load before reportsView.js")', source)
        self.assertIn('throw new Error("reports/auditView.js must load before reportsView.js")', source)
        self.assertIn('throw new Error("reports/auditCommands.js must load before reportsView.js")', source)
        self.assertIn('throw new Error("reports/triage.js must load before reportsView.js")', source)
        self.assertIn("window.mediaPipelineReportsView = {", source)

    def test_reports_tab_nav_binds_without_direct_child_panel_selector(self) -> None:
        shell_source = REPORTS_SHELL.read_text(encoding="utf-8")

        self.assertIn("function reportsTabButtons(page)", shell_source)
        self.assertIn("function reportsTabPanels(page)", shell_source)
        self.assertIn("Array.from(page.children)", shell_source)
        self.assertIn("if (!buttons.length) return;", shell_source)
        self.assertIn(
            'button.addEventListener("click", () => activateReportsTab(button.dataset.reportsTab || "failures"));',
            shell_source,
        )
        self.assertNotIn('":scope > .reports-tab-panel[data-reports-tab-panel]"', shell_source)
        self.assertNotIn("if (!buttons.length || !panels.length) return;", shell_source)

    def test_failure_marker_source_is_default_failures_refresh_mode(self) -> None:
        html = REPORTS_PAGE.read_text(encoding="utf-8")
        app_source = APP_JS.read_text(encoding="utf-8")

        self.assertIn('id="failure-source-markers" type="checkbox" checked', html)
        self.assertIn('const failureSourceMarkers = Boolean(byId("failure-source-markers")?.checked);', app_source)
        self.assertIn(
            'const failureQuery = `/api/failures?limit=100${failureSourceMarkers ? "&source=markers" : ""}`;',
            app_source,
        )
        self.assertIn('failureSourceMarkers.addEventListener("change", refreshAll)', app_source)

    def test_failure_artifact_storage_panel_and_toast_are_read_only(self) -> None:
        html = REPORTS_PAGE.read_text(encoding="utf-8")
        app_source = APP_JS.read_text(encoding="utf-8")
        reports_source = REPORTS_VIEW.read_text(encoding="utf-8")
        reports_state_source = REPORTS_STATE.read_text(encoding="utf-8")
        failure_commands_source = REPORTS_FAILURE_COMMANDS.read_text(encoding="utf-8")
        failure_view_source = REPORTS_FAILURE_VIEW.read_text(encoding="utf-8")
        index_source = INDEX_HTML.read_text(encoding="utf-8")
        toast_source = OPERATOR_TOAST.read_text(encoding="utf-8")
        styles = _read_component_styles()

        for snippet in (
            'id="failure-artifact-summary-panel"',
            'id="failure-artifact-storage-status"',
            'id="failure-artifact-total-size"',
            'id="failure-artifact-file-count"',
            'id="failure-artifact-oldest"',
            'id="failure-artifact-threshold"',
            'id="failure-artifact-storage-summary"',
            'id="failure-artifact-cleanup-disclosure"',
            'id="failure-artifact-cleanup-status"',
            'id="failure-artifact-cleanup-confirm-button"',
            'id="failure-artifact-cleanup-summary"',
            'id="failure-artifact-select-all"',
            'id="failure-artifact-largest-files"',
            '<th scope="col"><input id="failure-artifact-select-all"',
            "<th scope=\"col\">Size</th>",
            "<th scope=\"col\">Modified</th>",
        ):
            self.assertIn(snippet, html)
        self.assertIn('["failure artifacts", refreshGet("/api/failures/artifacts", refreshOptions), false]', app_source)
        self.assertIn('window.mediaPipelineReportsView?.renderFailureArtifactSummary?.(values["failure artifacts"])', app_source)
        self.assertIn('window.mediaPipelineOperatorToast?.showFailureArtifactWarning?.(values["failure artifacts"])', app_source)
        self.assertIn('failureArtifacts: values["failure artifacts"] || {}', app_source)
        self.assertIn("lastFailureArtifactSummary: {}", reports_state_source)
        self.assertIn("selectedFailureArtifactPaths: new Set()", reports_state_source)
        self.assertIn("lastFailureArtifactCleanupPreview: null", reports_state_source)
        self.assertIn("failureArtifactCleanupBusy: false", reports_state_source)
        self.assertIn("function renderFailureArtifactSummary", failure_view_source)
        self.assertIn("function selectVisibleFailureArtifacts", failure_view_source)
        self.assertIn("checkbox.dataset.failureArtifactPath", failure_view_source)
        self.assertIn("reportCompactPath(file.relative_path || file.path || file.name || \"\")", failure_view_source)
        self.assertIn("Delete policy: ${loaded ? artifactCleanupPolicyText(payload) : \"disabled\"}", failure_view_source)
        self.assertIn("Delete route: ${payload.cleanup_route_available ? \"available\" : \"unavailable\"}", failure_view_source)
        self.assertIn('apiPost("/api/failures/artifacts/cleanup", failureArtifactCleanupPayload(previewRequest))', failure_commands_source)
        self.assertIn("function failureArtifactCleanupRequest", failure_commands_source)
        self.assertIn("function updateFailureArtifactCleanupConfirmState", failure_commands_source)
        self.assertIn("FAILURE_ARTIFACT_CLEANUP_REASON", failure_commands_source)
        self.assertIn('mode: "selected_failure_artifacts"', failure_commands_source)
        self.assertIn("artifact_paths: artifactPaths", failure_commands_source)
        self.assertIn("artifact_paths: Array.isArray(request.artifact_paths) ? request.artifact_paths : []", failure_commands_source)
        self.assertIn("dry_run_fingerprint", failure_commands_source)
        self.assertNotIn("DELETE FAILURE ARTIFACTS", html)
        self.assertNotIn("failure-artifact-cleanup-preview-button", html)
        self.assertNotIn("failure-artifact-cleanup-reason", html)
        self.assertNotIn("failure-artifact-cleanup-confirm-text", html)
        self.assertNotIn("Delete ${plannedCount} failure artifact", failure_commands_source)
        self.assertIn("requestFailureArtifactCleanup,", reports_source)
        self.assertIn("renderFailureArtifactCleanupResult,", reports_source)
        self.assertIn("renderFailureArtifactSummary,", reports_source)
        self.assertIn("/assets/operatorToast.js", index_source)
        self.assertIn("window.mediaPipelineOperatorToast = {", toast_source)
        self.assertIn("showFailureArtifactWarning", toast_source)
        self.assertIn("mediapipeline.failureArtifactWarningToastShown", toast_source)
        self.assertIn("sessionStorage?.getItem", toast_source)
        self.assertIn('closeLabel = "Dismiss"', toast_source)
        self.assertIn('"Dismiss notice"', toast_source)
        self.assertIn('window.showPage("reports")', toast_source)
        self.assertIn('activateQuickLink?.("failure-all")', toast_source)
        self.assertIn('document.getElementById("failure-artifact-summary-panel")', toast_source)
        self.assertNotIn("apiPost(", toast_source)
        self.assertNotIn("fetch(", toast_source)
        self.assertIn(".operator-toast", styles)

    def test_failure_artifact_warning_toast_is_once_per_session_and_navigates(self) -> None:
        node = shutil.which("node")
        if not node:
            raise unittest.SkipTest("Node.js is required for the operator toast behavior smoke.")
        script = textwrap.dedent(
            r"""
            const fs = require("fs");
            const vm = require("vm");
            const source = fs.readFileSync("apps/desktop/webview/static/assets/operatorToast.js", "utf8");
            function makeElement(tag) {
              const node = {
                tagName: String(tag || "").toUpperCase(),
                children: [],
                dataset: {},
                className: "",
                attributes: {},
                parentElement: null,
                _textContent: "",
                appendChild(child) { child.parentElement = this; this.children.push(child); return child; },
                append(...items) { items.forEach((item) => this.appendChild(item)); },
                removeChild(child) {
                  this.children = this.children.filter((item) => item !== child);
                  child.parentElement = null;
                  return child;
                },
                setAttribute(name, value) { this.attributes[name] = String(value); },
                hasAttribute(name) { return Object.prototype.hasOwnProperty.call(this.attributes, name); },
                focus() {},
                scrollIntoView() {},
                addEventListener(name, handler) { this[`on${name}`] = handler; },
                click() { if (typeof this.onclick === "function") this.onclick({ target: this }); },
                querySelectorAll(selector) {
                  const results = [];
                  const walk = (item) => {
                    if (selector === "[data-toast-id]" && item.dataset.toastId) results.push(item);
                    item.children.forEach(walk);
                  };
                  this.children.forEach(walk);
                  return results;
                },
              };
              Object.defineProperty(node, "id", {
                get() { return this.attributes.id || ""; },
                set(value) { this.attributes.id = String(value); },
              });
              Object.defineProperty(node, "textContent", {
                get() { return this._textContent || this.children.map((child) => child.textContent || "").join(""); },
                set(value) { this._textContent = String(value ?? ""); this.children = []; },
              });
              return node;
            }
            const body = makeElement("body");
            const panel = makeElement("section");
            panel.id = "failure-artifact-summary-panel";
            body.appendChild(panel);
            function findById(node, id) {
              if (node.id === id) return node;
              for (const child of node.children) {
                const found = findById(child, id);
                if (found) return found;
              }
              return null;
            }
            function findByClass(node, needle) {
              if (String(node.className || "").split(/\s+/).includes(needle)) return node;
              for (const child of node.children) {
                const found = findByClass(child, needle);
                if (found) return found;
              }
              return null;
            }
            const storage = new Map();
            const calls = [];
            const context = {
              window: {},
              document: {
                body,
                createElement: makeElement,
                getElementById(id) { return findById(body, id); },
              },
              setTimeout() { return 0; },
              sessionStorage: {
                getItem(key) { return storage.get(key) || ""; },
                setItem(key, value) { storage.set(key, String(value)); },
                clear() { storage.clear(); },
              },
            };
            context.window = context;
            context.window.showPage = (page) => calls.push(["showPage", page]);
            context.window.mediaPipelineReportsView = {
              activateQuickLink(action) { calls.push(["activateQuickLink", action]); },
            };
            vm.createContext(context);
            vm.runInContext(source, context, { filename: "operatorToast.js" });
            const toast = context.window.mediaPipelineOperatorToast;
            if (!toast?.showFailureArtifactWarning) throw new Error("toast namespace missing");
            const warning = { warning: true, threshold_gb: 100, total_size_text: "101 GB" };
            if (toast.showFailureArtifactWarning(warning) !== true) throw new Error("first warning did not show");
            if (toast.showFailureArtifactWarning(warning) !== false) throw new Error("second warning was not suppressed");
            const region = context.document.getElementById("operator-toast-region");
            if (!region || region.children.length !== 1) throw new Error(`unexpected toast count ${region?.children.length}`);
            const action = findByClass(region, "operator-toast-action");
            if (!action) throw new Error("toast action missing");
            action.click();
            if (JSON.stringify(calls) !== JSON.stringify([["showPage", "reports"], ["activateQuickLink", "failure-all"]])) {
              throw new Error(`unexpected navigation calls ${JSON.stringify(calls)}`);
            }
            storage.clear();
            if (toast.showFailureArtifactWarning({ warning: true, threshold_gb: 0, total_size_text: "200 GB" }) !== false) {
              throw new Error("disabled threshold still showed a toast");
            }
            """
        )
        result = subprocess.run(
            [node, "-e", script],
            cwd=REPO_ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr or result.stdout)

    def test_marker_clear_is_guided_preview_first_flow(self) -> None:
        source = REPORTS_VIEW.read_text(encoding="utf-8")
        failure_commands_source = REPORTS_FAILURE_COMMANDS.read_text(encoding="utf-8")
        html = REPORTS_PAGE.read_text(encoding="utf-8")

        self.assertIn("Failure Resolution Center", html)
        self.assertIn("failure-resolution-groups", html)
        self.assertIn("failure-lifecycle-state", html)
        self.assertIn("failure-playbook-steps", html)
        self.assertIn("failure-verification-panel", html)
        self.assertIn("failure-timeline", html)
        self.assertIn("All error reports", html)
        self.assertIn('id="failure-all-records-disclosure" class="failure-records-panel"', html)
        self.assertIn("failure-records-table-wrap", html)
        self.assertNotIn('<details id="failure-all-records-disclosure"', html)
        self.assertLess(html.index("All error reports"), html.index('id="failure-lifecycle-strip"'))
        records_panel_start = html.index('id="failure-all-records-disclosure"')
        workflow_start = html.index('<section class="failure-resolution-workflow"', records_panel_start)
        records_panel_html = html[records_panel_start:workflow_start]
        self.assertIn("failure-records-table-wrap", records_panel_html)
        self.assertIn("failure-records-actions", records_panel_html)
        self.assertIn("failure-clear-scope", records_panel_html)
        self.assertIn("failure-archive-disclosure", records_panel_html)
        self.assertLess(
            records_panel_html.index("failure-records-table-wrap"),
            records_panel_html.index("failure-records-actions"),
        )
        self.assertNotIn("failure-lifecycle-resolve-preview-button", html)
        self.assertNotIn("failure-lifecycle-reopen-preview-button", html)
        self.assertIn("failure-lifecycle-resolve-confirm-button", html)
        self.assertIn("failure-clear-scope", html)
        self.assertNotIn("failure-clear-preview-button", html)
        self.assertNotIn("Preview clear", html)
        self.assertIn("Clear errors", html)
        self.assertIn('id="failure-clear-confirm-button" class="danger-button" disabled', html)
        self.assertIn('id="failure-archive-confirm-button" class="danger-button" disabled', html)
        self.assertIn("More evidence", html)
        self.assertIn("failure-evidence-links", html)
        self.assertIn('return { scope: "all_markers", marker_paths: []', failure_commands_source)
        self.assertIn("all_markers: true", failure_commands_source)
        self.assertIn("if (!request.all_markers) payload.marker_paths = request.marker_paths;", failure_commands_source)
        self.assertIn("Clear errors for the selected scope.", failure_commands_source)
        self.assertIn("failureClearPreviewKey(request)", failure_commands_source)
        self.assertIn("journal_key: journalKey", failure_commands_source)
        self.assertIn("Clearing all active errors.", failure_commands_source)
        self.assertIn("function setFailureMarkerSourceMode(enabled)", source)
        self.assertIn("setFailureMarkerSourceMode(true);", failure_commands_source)
        self.assertIn("function applyLocalFailureMarkerClear(request, result)", failure_commands_source)
        self.assertIn('apiPost("/api/failures/open", payload)', failure_commands_source)
        self.assertIn("requestFailureEvidenceOpen", failure_commands_source)
        self.assertIn("renderFailurePreview(nextPreview);", failure_commands_source)
        self.assertIn('apiPost("/api/failures/archive-evidence", request)', failure_commands_source)
        self.assertIn("Reason (optional)", html)
        self.assertIn("function updateFailureArchiveConfirmState()", failure_commands_source)
        self.assertIn("Archive evidence", html)

    def test_failure_lifecycle_operator_flow_is_direct_for_closure(self) -> None:
        failure_commands_source = REPORTS_FAILURE_COMMANDS.read_text(encoding="utf-8")
        failure_view_source = REPORTS_FAILURE_VIEW.read_text(encoding="utf-8")
        html = REPORTS_PAGE.read_text(encoding="utf-8")

        self.assertIn('apiPost("/api/failures/lifecycle", request)', failure_commands_source)
        self.assertIn("function requestFailureLifecycleTransition", failure_commands_source)
        self.assertIn("function updateFailureLifecycleConfirmState", failure_commands_source)
        self.assertIn("failureLifecyclePreviewKey(request)", failure_commands_source)
        self.assertNotIn("Preview resolve", html)
        self.assertIn("Mark resolved", html)
        self.assertNotIn("Preview reopen", html)
        self.assertNotIn("failure-lifecycle-reason", html)
        self.assertNotIn("failure-lifecycle-note", html)
        self.assertNotIn("Required for resolve, reopen, or waive", html)
        self.assertNotIn("Optional operator note", html)
        self.assertIn("failureLifecycleBackendReason", failure_commands_source)
        self.assertIn("confirm_transition", failure_commands_source)
        self.assertIn("dry_run_fingerprint", failure_commands_source)
        self.assertIn("confirmation_mode", failure_commands_source)
        self.assertIn("This writes only the failure resolution journal.", failure_commands_source)
        self.assertIn("handleReportsFailureKeyboard", failure_view_source)
        self.assertIn("moveFailureGroupSelection", failure_view_source)

    def test_audit_review_status_is_case_normalized_for_investigation_gate(self) -> None:
        triage_source = REPORTS_TRIAGE.read_text(encoding="utf-8")

        self.assertIn("const auditStatus = auditReviewStatus();", triage_source)
        self.assertIn('auditStatus.toLowerCase().includes("review")', triage_source)

    def test_reports_guardrail_copy_names_backend_marker_clear_exception(self) -> None:
        source = REPORTS_VIEW.read_text(encoding="utf-8")
        failure_commands_source = REPORTS_FAILURE_COMMANDS.read_text(encoding="utf-8")
        failure_model_source = REPORTS_FAILURE_MODEL.read_text(encoding="utf-8")

        self.assertNotIn("Reports remains read-only", source)
        self.assertIn("Reports triage is read-only", failure_model_source + REPORTS_TRIAGE.read_text(encoding="utf-8"))
        self.assertIn("Clear errors, then rerun after confirming logs.", failure_model_source)
        self.assertNotIn("Clear ${targetText}?", failure_commands_source)
        self.assertNotIn("Archive ${target}?", failure_commands_source)

    def test_row_keys_use_locale_invariant_lowercase(self) -> None:
        source = REPORTS_VIEW.read_text(encoding="utf-8")
        failure_model_source = REPORTS_FAILURE_MODEL.read_text(encoding="utf-8")
        audit_model_source = REPORTS_AUDIT_MODEL.read_text(encoding="utf-8")

        self.assertNotIn("toLocaleLowerCase", source + failure_model_source + audit_model_source)
        self.assertIn('].join("\\u001f").toLowerCase();', audit_model_source)

    def test_reports_audit_controls_are_backend_owned(self) -> None:
        source = REPORTS_VIEW.read_text(encoding="utf-8")
        state_source = REPORTS_STATE.read_text(encoding="utf-8")
        audit_view_source = REPORTS_AUDIT_VIEW.read_text(encoding="utf-8")
        audit_commands_source = REPORTS_AUDIT_COMMANDS.read_text(encoding="utf-8")
        html = REPORTS_PAGE.read_text(encoding="utf-8")

        self.assertIn("report-audit-start-library-root", html)
        self.assertIn("report-audit-library-root-picker-badge", html)
        self.assertIn('data-path-picker-target="reports.audit_library_root"', html)
        self.assertIn('data-path-picker-input="report-audit-start-library-root"', html)
        self.assertIn("report-audit-add-source-button", html)
        self.assertIn("report-audit-scan-selected-button", html)
        self.assertIn("report-audit-scan-all-button", html)
        self.assertIn("report-audit-select-all-sources-button", html)
        self.assertIn("report-audit-clear-source-selection-button", html)
        self.assertIn("report-audit-source-status", html)
        self.assertIn("report-audit-source-rows", html)
        self.assertIn("report-audit-source-selection-status", html)
        self.assertIn("Audit Sources", html)
        self.assertIn("Location to Scan", html)
        self.assertIn("Add Source", html)
        self.assertIn("Scan Selected", html)
        self.assertIn("<th scope=\"col\">Location</th>", html)
        self.assertIn("<th scope=\"col\">Status</th>", html)
        self.assertIn("<th scope=\"col\">Video Files</th>", html)
        self.assertIn("<th scope=\"col\">Sidecars</th>", html)
        self.assertIn("<th scope=\"col\">Folders</th>", html)
        self.assertIn("<th scope=\"col\">Last Scan</th>", html)
        self.assertIn("<th scope=\"col\">Actions</th>", html)
        self.assertNotIn("Shortcut", html)
        self.assertNotIn("Quick Stage", html)
        self.assertNotIn("Saved Locations", html)
        self.assertIn("report-audit-start-include-sidecars", html)
        self.assertIn("report-audit-start-show-console", html)
        self.assertIn("report-audit-start-button", html)
        self.assertIn("report-audit-stop-button", html)
        self.assertIn("report-audit-launch-preflight", html)
        self.assertIn("report-audit-launch-detail", html)
        self.assertIn("report-audit-score-policy-status", html)
        self.assertIn("report-audit-score-policy-save-button", html)
        self.assertIn("report-audit-score-policy-reset-button", html)
        self.assertIn("report-audit-ignore-selected-button", html)
        self.assertIn("report-audit-export-rerun-csv-button", html)
        self.assertIn("Build CSV Rerun Queue", html)
        self.assertNotIn("Selected Audit Row Actions", html)
        self.assertIn('role="toolbar" aria-label="Selected audit row actions"', html)
        self.assertIn('id="report-audit-export-status" class="inline-action-status"', html)
        self.assertIn('id="report-audit-export-rerun-csv-button" class="primary-button"', html)
        self.assertLess(
            html.index('aria-label="Selected audit row actions"'),
            html.index('id="audit-preview-rows"'),
        )
        self.assertIn('data-audit-selection-action="select-visible"', html)
        self.assertIn("data-audit-score-threshold-input", html)
        self.assertIn('data-audit-selection-action="select-score-at-least"', html)
        self.assertIn('data-audit-selection-action="clear"', html)
        self.assertIn("report-audit-export-detail", html)
        self.assertIn("<th scope=\"col\">Select</th>", html)
        self.assertIn("<summary>Advanced score controls</summary>", html)
        self.assertIn("<th scope=\"col\">Point issue</th>", html)
        self.assertIn("High issue-code marker", html)
        self.assertIn("Medium issue-code marker", html)
        self.assertNotIn("High issue: <code>ffprobe-open-failed</code>", html)
        self.assertNotIn("audio-default-policy-mismatch", html)
        self.assertNotIn('data-audit-score-policy-mirror="high_issue"', html)
        self.assertIn("data-advanced", html)
        self.assertIn('clearRows(tbody, 8, reportsState.lastAuditRows.length ? "No audit rows match the filter." : reportsState.lastAuditEmptyMessage)', audit_view_source)
        self.assertIn("function renderAuditControls", audit_view_source)
        self.assertIn("const reportsState = reportsStateModule.createReportsState();", source)
        self.assertIn("function createReportsState()", state_source)
        self.assertIn("selectedAuditRowKeys: new Set(),", state_source)
        self.assertIn("reportAuditCommandBusy: \"\",", state_source)
        self.assertIn("reportAuditAcceptedRun: null,", state_source)
        self.assertIn("lastReportAuditSources: {},", state_source)
        self.assertIn("selectedReportAuditSourceIds: new Set(),", state_source)
        self.assertIn("REPORT_AUDIT_POST_START_REFRESH_DELAYS_MS", audit_commands_source)
        self.assertIn("function setReportAuditCommandBusy", audit_commands_source)
        self.assertIn("function reportAuditBusyResult", audit_commands_source)
        self.assertIn("function renderReportAuditRunningState", audit_commands_source)
        self.assertIn("function reportAuditHasBackendActiveRunEvidence", audit_commands_source)
        self.assertIn("function reportAuditStaleProgressEvidence", audit_commands_source)
        self.assertIn("function renderReportAuditSources", audit_commands_source)
        self.assertIn("function addReportAuditSourceFromForm", audit_commands_source)
        self.assertIn('renderReportAuditSources(auditSources, result?.message || "");', audit_commands_source)
        self.assertIn('result?.message || "Audit source command failed."', audit_commands_source)
        self.assertIn("function removeReportAuditSource", audit_commands_source)
        self.assertIn("function scanReportAuditSources", audit_commands_source)
        self.assertIn("function selectAllReportAuditSources", audit_commands_source)
        self.assertIn("function clearReportAuditSourceSelection", audit_commands_source)
        self.assertIn("dataset.auditSourceAction", audit_commands_source)
        self.assertIn("library_roots:", audit_commands_source)
        self.assertIn("source_ids:", audit_commands_source)
        self.assertIn('apiPost("/api/audit/sources"', audit_commands_source)
        self.assertIn('apiPost("/api/audit/sources/scan"', audit_commands_source)
        self.assertNotIn("REPORT_AUDIT_SAVED_LOCATIONS_STORAGE_KEY", audit_commands_source)
        self.assertNotIn("localStorage", audit_commands_source)
        self.assertNotIn("shortcut", audit_commands_source.lower())
        self.assertIn("Audit Running", audit_commands_source)
        self.assertIn("Stop Audit", audit_commands_source)
        self.assertIn("No active audit run is visible to stop.", audit_commands_source)
        self.assertIn("Audit progress is stale and no active audit process is visible", audit_commands_source)
        self.assertIn("Stop Audit is unavailable until backend active-run evidence appears.", audit_commands_source)
        self.assertIn("ETA unavailable until backend progress reports file count", audit_commands_source)
        self.assertIn("Readiness preview: informational only; this is not a backend dry-run.", audit_commands_source)
        self.assertIn('apiPost("/api/audit/score-policy", request)', audit_commands_source)
        self.assertIn('apiPost("/api/audit/ignore", request)', audit_commands_source)
        self.assertIn('apiPost("/api/audit/export-rerun-csv", request)', audit_commands_source)
        self.assertIn("function handoffAuditRerunCsvToQueue", audit_commands_source)
        self.assertIn('window.showPage("queue")', audit_commands_source)
        self.assertIn('queueView.activateQueueTab("rerun", { persist: true })', audit_commands_source)
        self.assertIn("queueView.selectRerunCsvPathForPreview", audit_commands_source)
        self.assertIn("Start route remains /api/rerun/start; normal /api/pipeline/start is not used.", audit_commands_source)
        self.assertIn("function collectReportAuditStartRequest", audit_commands_source)
        self.assertIn("function startReportAuditFromForm", audit_commands_source)
        self.assertIn("function stopReportAuditFromForm", audit_commands_source)
        self.assertIn('apiPost("/api/audit/start", request)', audit_commands_source)
        self.assertIn('apiPost("/api/audit/stop"', audit_commands_source)
        self.assertIn("confirm_stop: true", audit_commands_source)
        self.assertIn("reason: request.reason", audit_commands_source)
        self.assertIn('"stopped"', audit_commands_source)
        self.assertIn("policy.issue_code_weights = {};", audit_commands_source)
        self.assertIn("data-audit-score-issue-code", audit_commands_source)
        self.assertIn('renderReportAuditIssueRows(score, "high", "rerun_bucket")', audit_view_source)
        self.assertIn('renderReportAuditIssueRows(score, "medium", "review_bucket")', audit_view_source)
        self.assertIn("function selectVisibleAuditRows", audit_view_source)
        self.assertIn("function selectAuditRowsAtOrAboveScore", audit_view_source)
        self.assertIn("auditScoreValue(row) >= threshold", audit_view_source)
        self.assertIn("[data-audit-selection-action]", audit_view_source)
        self.assertIn("row_keys: selectedAuditRowKeysList()", audit_commands_source)
        self.assertIn("window.mediaPipelineReportsView = {", source)
        self.assertIn("renderAuditControls,", source)

    def test_reports_ia_refresh_surface_is_discoverable_without_new_overview_tab(self) -> None:
        triage_source = REPORTS_TRIAGE.read_text(encoding="utf-8")
        html = REPORTS_PAGE.read_text(encoding="utf-8")
        styles = _read_component_styles()

        self.assertIn("<h2>Report Triage</h2>", html)
        self.assertIn('class="panel report-triage-panel" data-panel-type="evidence"', html)
        self.assertIn('.report-triage-panel[data-panel-type="evidence"] > .panel-heading h2::after', styles)
        self.assertIn("content: none;", styles)
        self.assertIn("report-triage-next-action", html)
        self.assertIn("report-triage-action-owner", html)
        self.assertIn("report-triage-report-state", html)
        self.assertIn('data-reports-tab="files" aria-selected="false">Locations</button>', html)
        self.assertNotIn('data-reports-tab="overview"', html)
        self.assertNotIn("report-go-rerun-button", html)
        self.assertNotIn("report-go-audit-button", html)
        self.assertNotIn("report-go-diagnostics-button", html)
        self.assertIn("function renderReportTriageBand", triage_source)
        self.assertIn("reportTriageBandNextAction", triage_source)

    def test_reports_audit_progress_panel_is_status_not_evidence(self) -> None:
        html = REPORTS_PAGE.read_text(encoding="utf-8")

        audit_progress_index = html.index("<h2>Audit Progress</h2>")
        audit_progress_section_start = html.rfind("<section", 0, audit_progress_index)
        audit_progress_open_tag = html[audit_progress_section_start:audit_progress_index]
        self.assertIn('data-panel-type="status"', audit_progress_open_tag)
        self.assertNotIn('data-panel-type="evidence"', audit_progress_open_tag)

    def test_reports_filters_and_row_owner_context_are_static_guarded(self) -> None:
        shared_source = REPORTS_SHARED.read_text(encoding="utf-8")
        shell_source = REPORTS_SHELL.read_text(encoding="utf-8")
        failure_model_source = REPORTS_FAILURE_MODEL.read_text(encoding="utf-8")
        failure_view_source = REPORTS_FAILURE_VIEW.read_text(encoding="utf-8")
        audit_model_source = REPORTS_AUDIT_MODEL.read_text(encoding="utf-8")
        audit_view_source = REPORTS_AUDIT_VIEW.read_text(encoding="utf-8")
        html = REPORTS_PAGE.read_text(encoding="utf-8")

        for chip in [
            "all",
            "needs_action",
            "working",
            "waiting_retry",
            "ready_to_clear",
            "resolved_recently",
        ]:
            self.assertIn(f'data-failure-filter-chip="{chip}"', html)
        for chip in ["rerun", "redownload", "review", "high", "subtitle", "audio", "duplicates"]:
            self.assertIn(f'data-audit-filter-chip="{chip}"', html)
        self.assertIn("<th scope=\"col\">Evidence</th>", html)
        self.assertIn("<th scope=\"col\">Owner</th>", html)
        self.assertIn('clearRows(tbody, 6, reportsState.lastFailureRows.length ? "No failure rows match the filter." : reportsState.lastFailureEmptyMessage)', failure_view_source)
        self.assertIn("function failureTableEvidenceText", failure_model_source)
        self.assertIn("function failureEvidenceProofLines", failure_model_source)
        self.assertIn("function failureEvidenceStreamLine", failure_model_source)
        self.assertIn("Structured proof", failure_view_source)
        self.assertIn("...failureEvidenceProofLines(item).slice(0, 8)", failure_model_source)
        self.assertIn("function failureActionOwner", failure_model_source)
        self.assertIn("function renderFailureResolutionGroups", failure_view_source)
        self.assertIn("function renderFailureResolutionDetail", failure_view_source)
        self.assertIn("function auditActionOwner", audit_model_source)
        self.assertIn("function hiddenSelectedFailureCount", failure_view_source)
        self.assertIn("function hiddenSelectedAuditCount", audit_view_source)
        self.assertIn("function hiddenSelectedCount", shared_source)
        self.assertIn("selected hidden by filter", shared_source)
        self.assertIn("showing first ${rowRenderLimit} of", shared_source)
        self.assertIn("setCellStatusChip(statusCell, failureStatusLabel(item), severity)", failure_view_source)
        self.assertIn("function reportOwnerPage", shell_source)
        self.assertIn("button.dataset.reportOwnerNavigate", shell_source)
        self.assertIn("Action owner:", audit_view_source)

    def test_reports_warnings_and_locations_are_actionable_support_evidence(self) -> None:
        triage_source = REPORTS_TRIAGE.read_text(encoding="utf-8")
        shell_source = REPORTS_SHELL.read_text(encoding="utf-8")
        html = REPORTS_PAGE.read_text(encoding="utf-8")

        self.assertIn("<h2>Actionable Warnings</h2>", html)
        self.assertIn("report-warning-rows", html)
        self.assertIn("<th scope=\"col\">Next Action</th>", html)
        self.assertIn("<h2>Latest Report Paths</h2>", html)
        self.assertIn("<h2>Report Roots</h2>", html)
        self.assertIn("report-open-history-disclosure", html)
        self.assertIn("function collectReportWarnings", shell_source)
        self.assertIn("function renderReportWarnings", shell_source)
        self.assertIn("reportCompactPath(item.path)", shell_source)
        self.assertIn("requestDiagnosticsOpen(target, button)", shell_source)
        self.assertIn("warningRows.length ? \"Review\" : \"Ready\"", triage_source)

    def test_failure_review_board_uses_tile_summary_with_detail_fallback(self) -> None:
        failure_model_source = REPORTS_FAILURE_MODEL.read_text(encoding="utf-8")
        failure_view_source = REPORTS_FAILURE_VIEW.read_text(encoding="utf-8")
        html = REPORTS_PAGE.read_text(encoding="utf-8")
        styles = _read_component_styles()

        self.assertIn("<h2>Failure Resolution Center</h2>", html)
        self.assertIn('id="failure-review-board" class="review-tile-board"', html)
        self.assertIn("Review board evidence", html)
        self.assertIn("failure-review-board-detail", html)
        self.assertIn("function failureReviewBoardTiles", failure_model_source)
        self.assertIn("Review State", failure_model_source)
        self.assertIn("Root Cause", failure_model_source)
        self.assertIn("Fix OCR path", failure_model_source)
        self.assertIn("failureReviewBoardTiles().map(failureReviewTileNode)", failure_view_source)
        self.assertIn(".review-tile-board", styles)
        self.assertIn(".review-tile-wide", styles)
        self.assertIn("@media (max-width: 520px)", styles)


if __name__ == "__main__":
    unittest.main()
