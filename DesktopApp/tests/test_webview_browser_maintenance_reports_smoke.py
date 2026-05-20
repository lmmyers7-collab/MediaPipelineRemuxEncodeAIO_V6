from __future__ import annotations

import json
import shutil
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from mediapipeline_desktop_app.api import LocalApiServer
from mediapipeline_desktop_app.application import MediaPipelineApplicationFacade

try:  # unittest discovery can import tests as top-level modules or package modules.
    from .test_application_facade import DummyWorkflowFacadeService
    from .test_webview_real_media_smoke import _write_fixture_state
    from .webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )
except ImportError:  # pragma: no cover - fallback for direct test execution
    from test_application_facade import DummyWorkflowFacadeService
    from test_webview_real_media_smoke import _write_fixture_state
    from webview_browser_smoke_support import (
        assert_media_no_mutation,
        browser_cdp_runner_prelude,
        capture_media_no_mutation_snapshot,
        find_browser as _find_browser,
        free_port as _free_port,
        run_node_browser_smoke,
    )


def _browser_maintenance_reports_runner_source() -> str:
    return browser_cdp_runner_prelude() + textwrap.dedent(
        r"""
        function maintenanceReportsScript() {
          return `
          (async () => {
            const posts = [];
            const originalApiPost = window.apiPost;
            window.apiPost = async (path, body, options) => {
              posts.push({ path: String(path || ""), body: body || {}, options: options || {} });
              return { ok: false, message: "maintenance/reports smoke blocks mutation posts" };
            };
            function byId(id) { return document.getElementById(id); }
            function text(id) { const node = byId(id); return node ? node.textContent || "" : ""; }
            function visiblePage(page) {
              return Boolean(document.querySelector('[data-page-panel="' + page + '"]')?.classList.contains("is-visible"));
            }
            function requireText(id, fragments) {
              const actual = text(id);
              for (const fragment of fragments) {
                if (!actual.includes(fragment)) throw new Error(id + " missing " + fragment + "\\nActual:\\n" + actual);
              }
            }
            function requireFunction(name) {
              if (typeof window[name] !== "function") throw new Error("missing global function " + name);
            }
            async function waitFor(predicate, label) {
              const deadline = Date.now() + 12000;
              let lastError = null;
              while (Date.now() < deadline) {
                try {
                  if (predicate()) return;
                } catch (error) {
                  lastError = error;
                }
                await new Promise((resolve) => setTimeout(resolve, 100));
              }
              throw new Error("Timed out waiting for " + label + (lastError ? ": " + lastError.message : "") + "\\nState:\\n" + [
                "maintenanceStatus=" + text("maintenance-status"),
                "maintenanceReadiness=" + text("maintenance-readiness"),
                "reportTriage=" + text("report-triage"),
                "failureSummary=" + text("failure-summary"),
                "auditSummary=" + text("audit-preview-summary"),
                "posts=" + JSON.stringify(posts),
              ].join("\\n"));
            }
            function clickFirst(selector, label) {
              const node = document.querySelector(selector);
              if (!node) throw new Error("missing " + label + " selector " + selector);
              node.click();
            }
            [
              "showPage",
              "renderMaintenance",
              "renderReleaseDryRunResult",
              "renderReleasePackageProgress",
              "releasePackageProgressBars",
              "renderBackfillDryRunResult",
              "renderBackfillProgress",
              "backfillProgressBars",
              "renderMaintenanceDryRunHistory",
              "renderReports",
              "renderFailurePreview",
              "renderAuditPreview",
              "getCommandHistory",
              "appendCommandResult",
            ].forEach(requireFunction);

            window.showPage("maintenance");
            await waitFor(
              () => visiblePage("maintenance") && !text("maintenance-readiness").includes("No maintenance readiness loaded."),
              "Maintenance health rendering",
            );
            requireText("maintenance-readiness", [
              "Real-media validation boundary:",
              "Mutation guardrail:",
            ]);
            clickFirst('#maintenance-rows tr[data-selectable-row="true"]', "maintenance row");
            requireText("maintenance-detail", [
              "Check:",
              "Dry-run impact:",
              "Guardrail:",
            ]);
            window.mediaPipelineMaintenanceView.renderReleaseDryRunResult({
              ok: true,
              command: "maintenance.release_dry_run",
              message: "Release dry run completed.",
              warnings: ["fixture release warning"],
              data: {
                dry_run: true,
                manifest_exists: false,
                zip_exists: false,
                destination_root: "C:/Temp/MediaPipeline_Deployable_DryRun",
                returncode: 0,
                elapsed_seconds: 1.25,
                command: "pwsh -File Build-MediaPipelineRemuxEncodeAIO-Release.ps1 -DryRun",
                release_progress: {
                  schema_version: "desktop_release_package_progress.v1",
                  status: "complete",
                  dry_run: true,
                  detail: "Release dry run completed; copy plan 12 file(s), excluded 3.",
                  updated_at: "2026-05-17T12:00:00",
                  steps: [
                    { key: "layout", label: "Layout", status: "complete", detail: "Destination planned." },
                    { key: "copy", label: "Copy plan", status: "complete", detail: "Dry-run copy plan reports 12 file(s) copied and 3 excluded." },
                    { key: "manifest", label: "Manifest", status: "skipped", detail: "Manifest write skipped by dry-run boundary." },
                    { key: "validate", label: "Validate", status: "complete", detail: "Release builder exited successfully." },
                    { key: "optional_smoke", label: "Optional smoke", status: "skipped", detail: "Verify/smoke is only planned in this WebView dry-run." },
                  ],
                  progress_bars: [{
                    id: "release_package",
                    label: "Release package",
                    mode: "stepped",
                    percent: 100,
                    status: "complete",
                    detail: "Release dry run completed; copy plan 12 file(s), excluded 3.",
                    source: "maintenance.release_dry_run",
                    updated_at: "2026-05-17T12:00:00",
                    stale: false,
                  }],
                },
                stdout: "Dry run only. No files copied.",
                stderr: "",
              },
            });
            requireText("release-dry-run-progress-bars", [
              "Release package",
              "100%",
              "source: maintenance.release_dry_run",
            ]);
            requireText("release-dry-run-detail", [
              "Dry-run trust summary:",
              "Writes manifest: no",
              "Writes zip: no",
              "Guardrail:",
              "Real-media boundary:",
            ]);
            window.mediaPipelineMaintenanceView.renderBackfillDryRunResult({
              ok: true,
              command: "maintenance.completed_backfill_dry_run",
              message: "Completed manifest backfill dry run completed.",
              data: {
                dry_run: true,
                writes_manifest: false,
                sidecars_ingested: 12,
                skipped_bad_json: 1,
                manifest_path: "C:/State/Completed/completed_jobs.jsonl",
                checkpoint_path: "C:/State/Completed/backfill_checkpoint.json",
                backfill_progress: {
                  schema_version: "desktop_maintenance_backfill_progress.v1",
                  status: "complete",
                  dry_run: true,
                  records_scanned: 13,
                  records_written: 0,
                  records_would_write: 12,
                  records_skipped: 1,
                  detail: "Backfill dry run scanned 13 record(s); would write 12; wrote 0.",
                  updated_at: "2026-05-17T12:00:00",
                  progress_bars: [{
                    id: "maintenance_backfill",
                    label: "Maintenance backfill",
                    mode: "determinate",
                    percent: 100,
                    status: "complete",
                    detail: "Backfill dry run scanned 13 record(s); would write 12; wrote 0.",
                    source: "maintenance.completed_backfill_dry_run",
                    updated_at: "2026-05-17T12:00:00",
                    stale: false,
                  }],
                },
                stdout: "Dry-run sidecar scan completed.",
              },
            });
            requireText("backfill-dry-run-progress-bars", [
              "Maintenance backfill",
              "100%",
              "source: maintenance.completed_backfill_dry_run",
            ]);
            requireText("backfill-dry-run-detail", [
              "Dry-run trust summary:",
              "Writes completed manifest: no",
              "Sidecars ingested: 12",
              "Skipped bad JSON: 1",
              "Guardrail:",
            ]);
            window.appendCommandResult({
              command: "maintenance.release_dry_run",
              ok: true,
              severity: "info",
              message: "Release dry run completed.",
              data: { dry_run: true, manifest_exists: false, zip_exists: false, returncode: 0, elapsed_seconds: 1.25 },
            });
            window.appendCommandResult({
              command: "maintenance.completed_backfill_dry_run",
              ok: true,
              severity: "info",
              message: "Completed manifest backfill dry run completed.",
              data: { dry_run: true, writes_manifest: false, sidecars_ingested: 12, skipped_bad_json: 1 },
            });
            window.mediaPipelineMaintenanceView.renderMaintenanceDryRunHistory(window.getCommandHistory());
            requireText("maintenance-dry-run-history", [
              "Release dry run",
              "Completed manifest backfill dry run",
            ]);

            window.showPage("reports");
            await waitFor(() => visiblePage("reports"), "Reports page visible");
            if (document.querySelector('[data-reports-tab="overview"]')?.getAttribute("aria-selected") !== "true") {
              throw new Error("Reports Overview tab was not selected by default.");
            }
            window.mediaPipelineReportsView.renderReports(
              {
                latest_paths: {
                  latest_failure_report: "C:/Reports/failures.txt",
                  latest_failure_json: "C:/Reports/failures.json",
                  latest_audit_csv: "C:/Reports/audit_summary.csv",
                  latest_priority_csv: "C:/Reports/audit_priority.csv",
                },
                warnings: [],
                audit_progress: {
                  status: "writing-reports",
                  processed_files: 10,
                  total_files: 10,
                  percent_complete: 100,
                  current_operation: "Writing CSV audit summary.",
                  report_stage: "write_csv",
                  report_step_index: 2,
                  report_step_total: 5,
                  report_completed_steps: ["classify", "write_json"],
                  latest_json_path: "C:/Reports/audit_summary.json",
                },
                progress_bars: [{
                  id: "audit_progress",
                  label: "Audit progress",
                  mode: "determinate",
                  percent: 100,
                  status: "active",
                  detail: "10 / 10 | Writing CSV audit summary.",
                  source: "audit_progress.json",
                  updated_at: "2026-05-17T12:00:00Z",
                }, {
                  id: "audit_reports",
                  label: "Audit reports",
                  mode: "stepped",
                  percent: 40,
                  status: "active",
                  detail: "2 / 5 | write csv | done: classify, write json",
                  source: "audit_progress.json",
                  updated_at: "2026-05-17T12:00:00Z",
                }],
              },
              {
                paths: {
                  failed_reports: "C:/Reports/Failures",
                  failed_markers: "C:/State/FailedMarkers",
                  audit_reports: "C:/Reports/Audit",
                  completed_manifest: "C:/State/Completed/completed_jobs.jsonl",
                  pending_push: "C:/PendingServerPush",
                  queue_snapshot: "C:/State/Progress/queue_snapshot.json",
                  active_jobs: "C:/State/ActiveJobs",
                },
              }
            );
            requireText("report-progress-summary", [
              "Audit status: writing-reports",
              "Report generation: 2 / 5 (write csv)",
              "Completed report steps: classify, write json",
              "Mutation guardrail:",
            ]);
            window.mediaPipelineReportsView.renderFailurePreview({
              source: "C:/Reports/failures.json",
              source_kind: "latest_json",
              count: 1,
              operator_required_count: 1,
              permanent_count: 0,
              transient_count: 0,
              warnings: ["fixture failure warning"],
              rows: [{
                source_json: "C:/Reports/failures.json",
                source_path: "C:/Source/Broken Movie.mkv",
                lookup_title: "Broken Movie",
                media_type: "movie",
                classification: "operator_required",
                error_code: "source_locked",
                stage: "source-stability",
                reason: "Source changed during probe.",
                suggested_action: "Wait for the source to stabilize before rerun.",
                suggested_rename: "",
                retry_count: 1,
                retry_limit: 3,
                recorded_at: "2026-05-14T22:00:00-04:00",
                artifact_path: "C:/Reports/source_locked.txt",
                repro_path: "C:/Source/Broken Movie.mkv",
              }],
            });
            window.mediaPipelineReportsView.renderAuditPreview({
              source: "C:/Reports/audit_priority.csv",
              priority_only: true,
              count: 1,
              high_priority_count: 1,
              rerun_count: 1,
              redownload_count: 0,
              review_count: 0,
              duplicate_group_count: 0,
              warnings: ["fixture audit warning"],
              rows: [{
                source_csv: "C:/Reports/audit_priority.csv",
                path: "C:/Outsource/TV/Serial Experiments Lain/Season 02/Serial Experiments Lain - S02E01 - Weird.mkv",
                relative_path: "TV/Serial Experiments Lain/Season 02/Serial Experiments Lain - S02E01 - Weird.mkv",
                lookup_title: "Serial Experiments Lain",
                media_type: "episode",
                effective_bucket: "RERUN_PIPELINE",
                priority_fix_level: "HIGH",
                priority_score: 95,
                primary_issue_code: "subtitle_missing_srt",
                primary_suggested_action: "Rerun pipeline for preferred-language SRT.",
                issue_messages: "Preferred-language SRT missing.",
              }],
            });
            requireText("report-triage", [
              "Failure JSON: present",
              "Audit CSV: present",
              "Failure rows: 1",
              "Audit rows: 1",
              "Mutation guardrail:",
            ]);
            requireText("report-investigation-checklist", [
              "Reports investigation checklist:",
              "Failure preview loaded: yes",
              "Audit preview loaded: yes",
              "Suggested investigation order:",
            ]);
            requireText("failure-review-board", [
              "Failure review board:",
              "Operator/permanent rows: 1",
              "source_locked",
              "Mutation guardrail:",
            ]);
            requireText("audit-preview-summary", [
              "Rows: 1",
              "High priority: 1",
              "Rerun: 1",
            ]);
            requireText("audit-review-board", [
              "Audit review board:",
              "Rerun rows: 1",
              "subtitle_missing_srt",
              "Mutation guardrail:",
            ]);
            clickFirst('[data-reports-tab="failures"]', "Reports Failures tab");
            if (document.querySelector('[data-reports-tab="failures"]')?.getAttribute("aria-selected") !== "true") {
              throw new Error("Reports Failures tab did not become selected.");
            }
            requireText("failure-rows", [
              "operator_required",
              "source-stability",
              "Source changed during probe.",
              "Wait for the source to stabilize before rerun.",
              "2026-05-14 22:00",
            ]);
            if (text("failure-rows").includes("2026-05-14T22:00:00-04:00")) {
              throw new Error("failure table still shows the long recorded timestamp");
            }
            const failureCheckbox = document.querySelector('#failure-rows input[type="checkbox"]');
            if (!failureCheckbox) throw new Error("failure row multi-select checkbox missing");
            failureCheckbox.click();
            if (!document.querySelector('#failure-rows input[type="checkbox"]')?.checked) {
              throw new Error("failure row multi-select checkbox did not stay checked");
            }
            clickFirst('#failure-rows tr[data-row-key]', "failure row");
            requireText("failure-detail", [
              "Reports failure selected row",
              "Class: operator_required",
              "Code: source_locked",
              "Suggested action: Wait for the source to stabilize before rerun.",
            ]);
            clickFirst('[data-reports-tab="audit"]', "Reports Audit tab");
            if (document.querySelector('[data-reports-tab="audit"]')?.getAttribute("aria-selected") !== "true") {
              throw new Error("Reports Audit tab did not become selected.");
            }
            clickFirst('#audit-preview-rows tr[data-row-key]', "audit row");
            requireText("audit-preview-detail", [
              "Reports audit selected row",
              "Bucket: RERUN_PIPELINE",
              "Issue: subtitle_missing_srt",
              "Suggested action: Rerun pipeline for preferred-language SRT.",
            ]);
            clickFirst('[data-reports-tab="overview"]', "Reports Overview tab");
            requireText("report-launch-handoff", [
              "Reports to Launch handoff:",
              "Status: Failure review first",
              "Candidate CSV paths: 2",
              "Mutation guardrail:",
            ]);
            byId("report-go-rerun-button").click();
            requireText("report-launch-handoff-action-status", [
              "Opened Launch > CSV Rerun",
              "Reports did not fill or submit it",
            ]);
            if (!visiblePage("launch")) throw new Error("Go To CSV Rerun did not navigate to Launch.");
            window.showPage("reports");
            byId("report-go-audit-button").click();
            requireText("audit-launch-progress-summary", [
              "Audit status: writing-reports",
              "Report generation: 2 / 5 (write csv)",
              "Mutation guardrail:",
            ]);
            if (!visiblePage("launch")) throw new Error("Go To Audit Launch did not navigate to Launch.");
            window.showPage("reports");
            byId("report-go-diagnostics-button").click();
            requireText("report-launch-handoff-action-status", [
              "Opened Diagnostics for read-only evidence review",
            ]);
            if (!visiblePage("diagnostics")) throw new Error("Go To Diagnostics did not navigate to Diagnostics.");

            const forbidden = [
              "/api/pipeline/start",
              "/api/audit/start",
              "/api/rerun/start",
              "/api/maintenance/release-dry-run",
              "/api/maintenance/release-build",
              "/api/maintenance/completed-backfill-dry-run",
              "/api/settings/save-patch",
              "/api/rename/apply",
              "/api/pending-publish/drain",
              "/api/failures/clear",
            ];
            const forbiddenPosts = posts.filter((entry) => forbidden.some((path) => entry.path.includes(path)));
            if (forbiddenPosts.length) throw new Error("maintenance/reports smoke posted mutation routes: " + JSON.stringify(forbiddenPosts));
            window.apiPost = originalApiPost;
            return {
              ok: true,
              posts,
              maintenanceStatus: text("maintenance-readiness-status"),
              reportStatus: text("report-triage-status"),
              failureStatus: text("failure-review-status"),
              auditStatus: text("audit-review-status"),
            };
          })()
          `;
        }

        async function main() {
          const userDataDir = fs.mkdtempSync(`${payload.tmpRoot.replace(/\\/g, "/")}/chrome-profile-`);
          const browser = launchBrowser([
            "--headless=new",
            "--disable-gpu",
            "--disable-background-networking",
            "--disable-default-apps",
            "--disable-extensions",
            "--disable-sync",
            "--metrics-recording-only",
            "--no-first-run",
            "--no-default-browser-check",
            `--remote-debugging-port=${payload.port}`,
            `--user-data-dir=${userDataDir}`,
            payload.url,
          ]);
          let client = null;
          try {
            const wsUrl = await waitForPageWebSocket(payload.port, payload.url);
            client = createCdpClient(wsUrl);
            await client.send("Runtime.enable");
            await client.send("Log.enable");
            await client.send("Page.enable");
            const deadline = Date.now() + 20000;
            while (Date.now() < deadline) {
              const ready = await client.send("Runtime.evaluate", {
                expression: `Boolean(document.getElementById("maintenance-readiness") && document.getElementById("report-triage") && typeof window.mediaPipelineMaintenanceView.renderMaintenance === "function" && typeof window.mediaPipelineReportsView.renderReports === "function" && typeof window.mediaPipelineReportsView.renderFailurePreview === "function" && typeof window.mediaPipelineReportsView.renderAuditPreview === "function")`,
                returnByValue: true,
              });
              if (ready.result?.value === true) break;
              await sleep(150);
            }
            const ready = await client.send("Runtime.evaluate", {
              expression: `Boolean(document.getElementById("maintenance-readiness") && document.getElementById("report-triage") && typeof window.mediaPipelineMaintenanceView.renderMaintenance === "function" && typeof window.mediaPipelineReportsView.renderReports === "function" && typeof window.mediaPipelineReportsView.renderFailurePreview === "function" && typeof window.mediaPipelineReportsView.renderAuditPreview === "function")`,
              returnByValue: true,
            });
            if (ready.result?.value !== true) throw new Error("Maintenance/Reports WebView globals or DOM nodes did not become ready.");
            const result = await client.send("Runtime.evaluate", {
              expression: maintenanceReportsScript(),
              awaitPromise: true,
              returnByValue: true,
            });
            if (result.exceptionDetails) {
              const details = result.exceptionDetails;
              throw new Error(details.exception?.description || details.exception?.value || details.text || "browser evaluation failed");
            }
            await sleep(750);
            const errorEvents = client.consoleEvents.filter((entry) => entry.startsWith("error:") || entry.startsWith("warning:"));
            if (client.exceptions.length || errorEvents.length) {
              throw new Error(`Browser console/exception noise: ${client.exceptions.concat(errorEvents).join("; ")}`);
            }
            console.log(JSON.stringify({ ok: true, result: result.result?.value || {} }));
          } finally {
            if (client) client.close();
            await terminateBrowser(browser);
          }
        }

        main().catch((error) => {
          console.error(error.stack || error.message || String(error));
          process.exit(1);
        });
        """
    )


def _run_browser_maintenance_reports_smoke(*, browser_path: str, url: str) -> dict[str, object]:
    node = shutil.which("node")
    if not node:
        raise unittest.SkipTest("Node.js is required for the browser-backed WebView maintenance/reports smoke.")
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as raw_tmp:
        tmp = Path(raw_tmp)
        port = _free_port()
        payload_path = tmp / "browser-maintenance-reports-payload.json"
        runner_path = tmp / "browser-maintenance-reports-runner.cjs"
        payload_path.write_text(
            json.dumps(
                {
                    "browserPath": browser_path,
                    "port": port,
                    "tmpRoot": str(tmp),
                    "url": url,
                },
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        runner_path.write_text(_browser_maintenance_reports_runner_source(), encoding="utf-8")
        return run_node_browser_smoke(
            "Browser-backed WebView Maintenance/Reports smoke",
            node=node,
            runner_path=runner_path,
            payload_path=payload_path,
            timeout_seconds=60,
        )


class WebViewBrowserMaintenanceReportsSmokeTests(unittest.TestCase):
    def test_real_browser_renders_maintenance_and_reports_operator_evidence_without_mutation_posts(self) -> None:
        browser_path = _find_browser()
        if not browser_path:
            raise unittest.SkipTest("Chrome or Edge is required for the browser-backed WebView maintenance/reports smoke.")

        with tempfile.TemporaryDirectory() as raw_root:
            root = Path(raw_root)
            resolved, _source, _output = _write_fixture_state(root)
            media_snapshot = capture_media_no_mutation_snapshot(root)
            service = DummyWorkflowFacadeService(root)
            facade = MediaPipelineApplicationFacade(service, app_version="v5-test")
            server = LocalApiServer(
                facade,
                token="browser-maintenance-reports-token",
                resolved_provider=lambda: resolved,
                audit_root_provider=lambda: str(root),
            )
            try:
                server.start()
                result = _run_browser_maintenance_reports_smoke(browser_path=browser_path, url=f"{server.url}/")
            finally:
                server.stop()
            assert_media_no_mutation(self, media_snapshot)

        browser_result = result["result"]
        self.assertEqual(browser_result["posts"], [])
        self.assertIn(browser_result["maintenanceStatus"], {"Ready", "Warnings", "Blocked"})
        self.assertEqual(browser_result["reportStatus"], "Action needed")
        self.assertEqual(browser_result["failureStatus"], "Action needed")
        self.assertEqual(browser_result["auditStatus"], "Rerun review")


if __name__ == "__main__":
    unittest.main()
